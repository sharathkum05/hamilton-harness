"""HTTP API in front of the harness.

    GET  /api/config                        who the rep is and how the widget looks
    POST /api/conversations                 start a conversation
    GET  /api/conversations/{id}            transcript, to redraw after a reload

The browser only ever sends customer text. Everything that decides what the
rep may do stays on the server.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from repkit.runtime import Agent
from repkit.web.sessions import Session, SessionStore


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
) -> FastAPI:
    pack = agent.pack
    store = sessions or SessionStore()
    app = FastAPI(title=f"{pack.persona.company} chat", docs_url=None, redoc_url=None)
    app.state.sessions = store

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
        return {
            "rep": {"name": persona.name, "company": persona.company, "role": persona.role},
            # Shown under the rep's name so nobody has to ask what they are talking to.
            "disclosure": "AI assistant",
            "widget": widget.model_dump(),
            "debug": debug,
        }

    @app.post("/api/conversations", status_code=201)
    def start_conversation() -> dict[str, Any]:
        session = store.create(agent.start())
        session.say("rep", pack.widget.greeting)
        return _public_session(session)

    @app.get("/api/conversations/{session_id}")
    def get_conversation(session_id: str) -> dict[str, Any]:
        return _public_session(session_or_404(session_id))

    return app
