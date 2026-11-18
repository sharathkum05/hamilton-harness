"""The dashboard's API: read and edit the pack that is being served.

Every route needs the admin: either the admin token, sent as a bearer token by
scripts and links, or the cookie set by signing in with the admin email and
password (see auth.py). A public demo can instead open the dashboard to
anyone, read-only, showing each visitor only the chats they started. The
editing itself is done by PackEditor,
which validates each change, writes it to the pack's own file and rolls it
back if the pack would no longer load. After a successful edit the running
rep is reloaded.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import time
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import AliasChoices, BaseModel, Field

from hamilton_harness.editor import (
    MAX_KNOWLEDGE_CHARS,
    EditError,
    PackEditor,
    dump_yaml,
)
from hamilton_harness.flow import STAGES, stages_from_events
from hamilton_harness.pack import PackError
from hamilton_harness.records import MemoryRecordStore, Status
from hamilton_harness.runtime import Agent
from hamilton_harness.setup import apply_setup, needs_setup, read_answers
from hamilton_harness.stats import overview
from hamilton_harness.web.auth import (
    COOKIE,
    SESSION_SECONDS,
    Account,
    Credentials,
    FailureCounter,
    SessionSigner,
)
from hamilton_harness.web.sessions import VISITOR_COOKIE, Visitors

MAX_LOGO_BYTES = 512_000
LOGO_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}
_UNSAFE_SVG = re.compile(rb"<script|javascript:|\son\w+\s*=|<foreignObject", re.IGNORECASE)


class StatusChange(BaseModel):
    status: Status


class KnowledgeText(BaseModel):
    text: str = Field(max_length=MAX_KNOWLEDGE_CHARS)


class FlowMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class SignIn(BaseModel):
    # "email" and "password" are the older names, still accepted.
    user: str = Field(max_length=254, validation_alias=AliasChoices("user", "email"))
    passcode: str = Field(max_length=1024, validation_alias=AliasChoices("passcode", "password"))


class PasscodeChange(BaseModel):
    current: str = Field(max_length=1024)
    new: str = Field(max_length=1024)


def _wait(seconds: int) -> str:
    minutes = -(-seconds // 60)
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def _looks_like(content_type: str, data: bytes) -> bool:
    """Check the bytes are the image the upload claims to be."""
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if content_type == "image/svg+xml":
        return b"<svg" in data[:2000].lower() and not _UNSAFE_SVG.search(data)
    return False


def _refuse(error: EditError) -> HTTPException:
    return HTTPException(status_code=404 if error.missing else 422, detail=str(error))


def _same_site(request: Request) -> bool:
    """Whether a browser request came from a page on this server."""
    origin = request.headers.get("origin")
    if origin is None:
        # Browsers send Origin on every request that changes something; tools do not.
        return True
    return origin.split("://", 1)[-1] == request.headers.get("host", "")


# Running the fake customers, a test message or a tool keeps nothing, so a demo
# visitor may. A test message already runs the same tools.
_SAFE_IN_DEMO = {"/api/admin/sim", "/api/admin/flow/try"}
_TRY_TOOL = re.compile(r"/api/admin/tools/[a-z][a-z0-9_]*/try")


def _safe_in_demo(path: str) -> bool:
    return path in _SAFE_IN_DEMO or bool(_TRY_TOOL.fullmatch(path))


READ_ONLY = "This is a read-only demo, so changes are not saved. Run Hamilton yourself to edit."


class _Only:
    """A visitor's own slice of the traces and records, for the public demo."""

    def __init__(self, traces: Any, records: Any, conversation_ids: set[str]) -> None:
        self._traces, self._records, self._ids = traces, records, conversation_ids

    def conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        everything = self._traces.conversations(limit=500) if self._traces else []
        return [c for c in everything if c["id"] in self._ids][:limit]

    def events(self, conversation_id: str) -> list[dict[str, Any]] | None:
        if conversation_id not in self._ids or not self._traces:
            return None
        return self._traces.events(conversation_id)

    def list(self, type_name: str | None = None) -> list[Any]:
        return [r for r in self._records.list(type_name) if r.conversation_id in self._ids]


def install_admin(
    app: FastAPI,
    holder: Any,
    token: str,
    credentials: Credentials | Account | None = None,
    *,
    visitors: Visitors | None = None,
) -> None:
    """Add the dashboard routes to `app`, guarded by `token`, and by a password if given.

    With `visitors`, the dashboard is a public, read-only demo instead.
    """
    demo = visitors is not None
    account = Account(credentials) if isinstance(credentials, Credentials) else credentials
    # Keyed on the token, so changing the token also signs everyone out.
    signer = SessionSigner(hashlib.sha256(f"session:{token}".encode()).hexdigest())
    failures = FailureCounter()

    def token_ok(authorization: str | None) -> bool:
        supplied = (authorization or "").removeprefix("Bearer ").strip()
        # compare_digest: the time taken must not reveal how much of the token matched.
        return bool(supplied) and secrets.compare_digest(supplied.encode(), token.encode())

    def signed_in(request: Request, authorization: str | None) -> str | None:
        if demo:
            return "demo"
        if token_ok(authorization):
            return "token"
        return signer.verify(request.cookies.get(COOKIE)) if account else None

    def require_admin(request: Request, authorization: str | None = Header(default=None)) -> None:
        who = signed_in(request, authorization)
        if who is None:
            raise HTTPException(status_code=401, detail="sign in to use the dashboard")
        # Looking and running the fake customers are fine; nothing a visitor does is kept.
        changes = request.method not in ("GET", "HEAD")
        if who == "demo" and changes and not _safe_in_demo(request.url.path):
            raise HTTPException(status_code=403, detail=READ_ONLY)
        # A cookie goes with any request the browser makes, so a change has to come
        # from this site's own pages. A bearer token is only sent on purpose.
        if who != "token" and request.method not in ("GET", "HEAD") and not _same_site(request):
            raise HTTPException(status_code=403, detail="request from another site refused")

    @app.get("/api/admin/session")
    def get_session(
        request: Request, authorization: str | None = Header(default=None)
    ) -> dict[str, Any]:
        who = signed_in(request, authorization)
        if who is None:
            raise HTTPException(
                status_code=401,
                detail="sign in to use the dashboard",
                headers={"x-hamilton-password": "on" if account else "off"},
            )
        if who == "demo":
            return {"user": None, "password": False, "demo": True, "expires_at": None}
        session = signer.read(request.cookies.get(COOKIE)) if who != "token" else None
        return {
            # None when signed in with the admin token, which belongs to no one.
            "user": None if who == "token" else who,
            "password": account is not None,
            "demo": False,
            "expires_at": session[1] if session else None,
            "can_change_passcode": bool(account and not account.fixed),
            "passcode_note": account.fixed if account else "",
        }

    @app.post("/api/admin/session")
    def sign_in(body: SignIn, request: Request, response: Response) -> dict[str, Any]:
        if account is None:
            raise HTTPException(
                status_code=400,
                detail="signing in with a passcode is not set up here. Use the admin token.",
            )
        address = request.client.host if request.client else "unknown"
        wait = failures.retry_after(address)
        if wait:
            raise HTTPException(
                status_code=429,
                detail=f"too many failed sign-ins. Try again in {_wait(wait)}.",
                headers={"Retry-After": str(wait)},
            )
        if not account.check(body.user, body.passcode):
            failures.fail(address)
            raise HTTPException(status_code=401, detail="that user ID and passcode do not match")
        failures.clear(address)
        response.set_cookie(
            COOKIE,
            signer.issue(account.user),
            max_age=SESSION_SECONDS,
            path="/api/admin",
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
        )
        return {"user": account.user, "expires_at": int(time.time()) + SESSION_SECONDS}

    @app.delete("/api/admin/session")
    def sign_out(response: Response) -> dict[str, Any]:
        response.delete_cookie(COOKIE, path="/api/admin", httponly=True, samesite="strict")
        return {"signed_out": True}

    router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

    @router.post("/passcode")
    def change_passcode(body: PasscodeChange, request: Request) -> dict[str, Any]:
        """Set a new admin passcode. Sessions already signed in stay signed in."""
        if account is None:
            raise HTTPException(status_code=400, detail="there is no passcode on this server")
        address = request.client.host if request.client else "unknown"
        wait = failures.retry_after(address)
        if wait:
            raise HTTPException(
                status_code=429,
                detail=f"too many wrong passcodes. Try again in {_wait(wait)}.",
                headers={"Retry-After": str(wait)},
            )
        try:
            account.change(body.current, body.new)
        except PermissionError as error:
            # A wrong current passcode counts like a failed sign-in.
            failures.fail(address)
            raise HTTPException(status_code=403, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"changed": True}

    def visible(request: Request) -> Any:
        """The traces and records this request may see: all of them, or a visitor's own."""
        if not demo:
            return holder.agent.traces, holder.agent.records
        mine = visitors.conversations(request.cookies.get(VISITOR_COOKIE))
        only = _Only(holder.agent.traces, holder.agent.records, mine)
        return only, only

    def editor() -> PackEditor:
        return PackEditor(holder.pack.root, on_change=holder.reload)

    @router.get("/pack")
    def get_pack() -> dict[str, Any]:
        return {**editor().overview(), "setup_pending": needs_setup(holder.pack.root)}

    @router.post("/setup")
    def run_setup(answers: dict[str, Any]) -> dict[str, Any]:
        """Rebuild the rep from the setup answers. Everything but the logo starts again."""
        try:
            apply_setup(holder.pack.root, read_answers(answers))
        except PackError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        holder.reload()
        return {"saved": "setup"}

    @router.put("/pack/policies")
    def put_policies(rules: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            saved = editor().save_policies(rules)
        except EditError as error:
            raise _refuse(error) from error
        return {"saved": "policies", "count": len(saved)}

    @router.put("/pack/tools")
    def put_tools(tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Replace the tools set up without code, the calls to the company's own web API."""
        try:
            saved = editor().save_api_tools(tools)
        except EditError as error:
            raise _refuse(error) from error
        return {"saved": "tools", "count": len(saved)}

    @router.post("/tools/{name}/try")
    def try_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run one tool with given inputs, as the rep would, and show what came back."""
        registry = holder.agent.tools
        if registry.spec(name) is None:
            raise HTTPException(status_code=404, detail=f"no tool called {name}")
        if name.startswith("create_") and any(r.tool_name == name for r in holder.pack.records):
            raise HTTPException(
                status_code=422, detail="records are taken in a chat, so they are not tried here"
            )
        outcome = registry.call(name, arguments)
        return {"ok": outcome.ok, "result": outcome.content}

    @router.put("/pack/{section}")
    def put_section(section: str, values: dict[str, Any]) -> dict[str, Any]:
        try:
            editor().save_section(section, values)
        except EditError as error:
            raise _refuse(error) from error
        return {"saved": section}

    @router.put("/knowledge/{name}")
    def put_knowledge(name: str, body: KnowledgeText) -> dict[str, Any]:
        try:
            editor().save_knowledge(name, body.text)
        except EditError as error:
            raise _refuse(error) from error
        return {"saved": name}

    @router.delete("/knowledge/{name}")
    def delete_knowledge(name: str) -> dict[str, Any]:
        try:
            editor().delete_knowledge(name)
        except EditError as error:
            raise _refuse(error) from error
        return {"deleted": name}

    @router.put("/logo")
    async def put_logo(request: Request) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        extension = LOGO_EXTENSIONS.get(content_type)
        if extension is None:
            raise HTTPException(status_code=415, detail="logo must be a png, jpg, webp or svg")
        data = await request.body()
        if not data or len(data) > MAX_LOGO_BYTES:
            raise HTTPException(status_code=413, detail="logo must be under 500 KB")
        if not _looks_like(content_type, data):
            raise HTTPException(
                status_code=422, detail="that file is not a safe image of that type"
            )

        edit = editor()
        brand = edit.root / "brand"
        brand.mkdir(exist_ok=True)
        for old in brand.glob("logo.*"):
            old.unlink()
        (brand / f"logo.{extension}").write_bytes(data)
        try:
            edit.update_section("widget", {"logo": f"brand/logo.{extension}"})
        except EditError as error:
            raise _refuse(error) from error
        return {"saved": f"brand/logo.{extension}"}

    @router.delete("/logo")
    def delete_logo() -> dict[str, Any]:
        edit = editor()
        for old in (edit.root / "brand").glob("logo.*"):
            old.unlink()
        edit.update_section("widget", {"logo": ""})
        return {"deleted": "logo"}

    @router.post("/sim")
    def run_sim() -> dict[str, Any]:
        try:
            return editor().run_fake_customers()
        except EditError as error:
            raise _refuse(error) from error

    @router.get("/flow")
    def get_flow() -> dict[str, Any]:
        """The stages of a turn, in the order they run."""
        return {"stages": [{"key": k, "name": n, "does": d} for k, n, d in STAGES]}

    @router.post("/flow/try")
    def try_flow(body: FlowMessage) -> dict[str, Any]:
        """Send one test message through the rep and say what each stage did with it."""
        agent = holder.agent
        # A fresh customer, and orders kept nowhere: a test leaves no trace in the inbox.
        trial = Agent(agent.pack, agent.model, records=MemoryRecordStore(), retry_wait=0)
        result = trial.respond(trial.start(), body.text)
        events = [{"kind": e.kind, **e.data} for e in result.events]
        return {
            "stages": stages_from_events(events, agent.pack),
            "bubbles": [bubble.text for bubble in result.bubbles],
        }

    @router.get("/overview")
    def get_overview(request: Request) -> dict[str, Any]:
        """Counts, a two-week timeline and the latest items, for the dashboard's first screen."""
        return overview(*visible(request))

    @router.get("/records")
    def list_records(request: Request, type: str | None = None) -> dict[str, Any]:
        """What the rep has taken down: orders, quotation requests and the like."""
        records = visible(request)[1]
        return {"records": [asdict(record) for record in records.list(type)]}

    @router.patch("/records/{record_id}")
    def update_record(record_id: str, change: StatusChange) -> dict[str, Any]:
        record = holder.agent.records.set_status(record_id, change.status)
        if record is None:
            raise HTTPException(status_code=404, detail="no such record")
        return asdict(record)

    @router.get("/conversations")
    def conversations(request: Request) -> dict[str, Any]:
        traces = visible(request)[0]
        return {"conversations": traces.conversations() if traces else []}

    @router.get("/conversations/{conversation_id}")
    def conversation(request: Request, conversation_id: str) -> dict[str, Any]:
        traces = visible(request)[0]
        events = traces.events(conversation_id) if traces else None
        if events is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        return {"id": conversation_id, "events": events}

    app.include_router(router)


__all__ = ["dump_yaml", "install_admin"]
