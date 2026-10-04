"""HTTP API in front of the harness.

    GET  /api/config                        who the rep is and how the widget looks
    POST /api/conversations                 start a conversation
    GET  /api/conversations/{id}            transcript, to redraw after a reload
    POST /api/conversations/{id}/messages   send a customer message, get the reply
    GET  /api/conversations/{id}/trace      every step of every turn (debug only)
    GET  /                                  demo page with the widget
    GET  /widget.js                         the embeddable widget

The browser only ever sends customer text. Everything that decides what the
rep may do stays on the server.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from repkit.pack.schema import Pack
from repkit.runtime import Agent, TurnResult
from repkit.web.sessions import Session, SessionStore

MAX_MESSAGE_CHARS = 2000
STATIC_DIR = Path(__file__).parent / "static"


class CustomerMessage(BaseModel):
    text: str = Field(max_length=MAX_MESSAGE_CHARS)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message is empty")
        return value


LOGO_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def logo_path(pack: Pack) -> Path | None:
    """The pack's logo file, if it names one that exists inside the pack."""
    if not pack.widget.logo or not pack.root:
        return None
    root = Path(pack.root).resolve()
    path = (root / pack.widget.logo).resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


def _debug_view(result: TurnResult) -> dict[str, Any]:
    """What the inspector shows: why the rep answered the way it did."""
    context = next((e.data for e in result.events if e.kind == "context"), {})
    return {
        "context": {"rules": context.get("rules", []), "notes": context.get("notes", [])},
        "actions": [
            {
                "tool": action.tool,
                "arguments": action.arguments,
                "outcome": action.outcome,
                "detail": action.detail,
                "rules": list(action.rule_ids),
            }
            for action in result.actions
        ],
        "replaced_by": result.replaced_by,
        "refused": result.refused,
        "handoff": (
            {"reason": result.handoff.reason, "detail": result.handoff.detail}
            if result.handoff
            else None
        ),
        "model_calls": result.model_calls,
        "latency_ms": round(result.latency_ms, 1),
        "tokens": {"input": result.usage.input_tokens, "output": result.usage.output_tokens},
    }


def _public_session(session: Session) -> dict[str, Any]:
    return {
        "id": session.id,
        "transcript": session.transcript,
        "handed_off": session.conversation.handed_off,
    }


def create_app(
    agent: Agent,
    *,
    debug: bool = False,
    sessions: SessionStore | None = None,
    allow_origins: Sequence[str] = (),
) -> FastAPI:
    """Build the app.

    `allow_origins` lists the sites allowed to embed the widget. Leave it empty
    when the widget is served from this same server.
    """
    pack = agent.pack
    store = sessions or SessionStore()
    app = FastAPI(title=f"{pack.persona.company} chat", docs_url=None, redoc_url=None)
    app.state.sessions = store
    if allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(allow_origins),
            allow_methods=["GET", "POST"],
            allow_headers=["content-type"],
        )

    def session_or_404(session_id: str) -> Session:
        session = store.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="conversation not found or expired")
        return session

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        persona, widget = pack.persona, pack.widget
        logo = logo_path(pack)
        settings = widget.model_dump(exclude={"logo"})
        # The version changes when the file does, so browsers pick up a new logo.
        settings["logo_url"] = f"/brand/logo?v={int(logo.stat().st_mtime)}" if logo else ""
        return {
            "rep": {"name": persona.name, "company": persona.company, "role": persona.role},
            # Shown under the rep's name so nobody has to ask what they are talking to.
            "disclosure": "AI assistant",
            "widget": settings,
            "debug": debug,
        }

    @app.get("/brand/logo", include_in_schema=False)
    def brand_logo() -> FileResponse:
        logo = logo_path(pack)
        if logo is None:
            raise HTTPException(status_code=404, detail="no logo")
        return FileResponse(
            logo,
            media_type=LOGO_TYPES[logo.suffix.lower()],
            # An SVG can carry script. Sandboxing it makes it an image and nothing more.
            headers={
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.post("/api/conversations", status_code=201)
    def start_conversation() -> dict[str, Any]:
        session = store.create(agent.start())
        session.say("rep", pack.widget.greeting)
        return _public_session(session)

    @app.get("/api/conversations/{session_id}")
    def get_conversation(session_id: str) -> dict[str, Any]:
        return _public_session(session_or_404(session_id))

    @app.post("/api/conversations/{session_id}/messages")
    def send_message(session_id: str, message: CustomerMessage) -> dict[str, Any]:
        session = session_or_404(session_id)
        # One message at a time: a second request mid-turn would interleave the history.
        if not session.lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="still answering the last message")
        try:
            session.say("customer", message.text)
            result = agent.respond(session.conversation, message.text)
            for bubble in result.bubbles:
                session.say("rep", bubble.text)
            session.turns.append([{"kind": e.kind, **e.data} for e in result.events])
        finally:
            session.lock.release()

        body: dict[str, Any] = {
            "bubbles": [{"text": b.text, "delay": b.delay} for b in result.bubbles],
            "handed_off": session.conversation.handed_off,
        }
        if debug:
            body["debug"] = _debug_view(result)
        return body

    @app.get("/api/conversations/{session_id}/trace")
    def get_trace(session_id: str) -> dict[str, Any]:
        if not debug:
            # Traces hold tool results and rule ids, so they stay off unless asked for.
            raise HTTPException(status_code=404, detail="not found")
        return {"turns": session_or_404(session_id).turns}

    @app.get("/", include_in_schema=False)
    def demo_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/widget.js", include_in_schema=False)
    def widget_script() -> FileResponse:
        return FileResponse(STATIC_DIR / "widget.js", media_type="text/javascript")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
