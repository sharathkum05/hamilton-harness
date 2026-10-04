"""The dashboard's API: read and edit the pack that is being served.

Every route needs the admin token. The editing itself is done by PackEditor,
which validates each change, writes it to the pack's own file and rolls it
back if the pack would no longer load. After a successful edit the running
rep is reloaded.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from hamilton_harness.editor import (
    MAX_KNOWLEDGE_CHARS,
    EditError,
    PackEditor,
    dump_yaml,
    list_conversations,
    read_conversation,
)
from hamilton_harness.records import Status
from hamilton_harness.stats import overview

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


def install_admin(app: FastAPI, holder: Any, token: str) -> None:
    """Add the dashboard routes to `app`, guarded by `token`."""

    def require_admin(authorization: str | None = Header(default=None)) -> None:
        supplied = (authorization or "").removeprefix("Bearer ").strip()
        # compare_digest: the time taken must not reveal how much of the token matched.
        if not supplied or not secrets.compare_digest(supplied.encode(), token.encode()):
            raise HTTPException(status_code=401, detail="admin token required")

    router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

    def editor() -> PackEditor:
        return PackEditor(holder.pack.root, on_change=holder.reload)

    @router.get("/pack")
    def get_pack() -> dict[str, Any]:
        return editor().overview()

    @router.put("/pack/policies")
    def put_policies(rules: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            saved = editor().save_policies(rules)
        except EditError as error:
            raise _refuse(error) from error
        return {"saved": "policies", "count": len(saved)}

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

    @router.get("/overview")
    def get_overview() -> dict[str, Any]:
        """Counts, a two-week timeline and the latest items, for the dashboard's first screen."""
        return overview(holder.agent.trace_dir, holder.agent.records)

    @router.get("/records")
    def list_records(type: str | None = None) -> dict[str, Any]:
        """What the rep has taken down: orders, quotation requests and the like."""
        return {"records": [asdict(record) for record in holder.agent.records.list(type)]}

    @router.patch("/records/{record_id}")
    def update_record(record_id: str, change: StatusChange) -> dict[str, Any]:
        record = holder.agent.records.set_status(record_id, change.status)
        if record is None:
            raise HTTPException(status_code=404, detail="no such record")
        return asdict(record)

    @router.get("/conversations")
    def conversations() -> dict[str, Any]:
        return {"conversations": list_conversations(holder.agent.trace_dir)}

    @router.get("/conversations/{conversation_id}")
    def conversation(conversation_id: str) -> dict[str, Any]:
        try:
            events = read_conversation(holder.agent.trace_dir, conversation_id)
        except EditError as error:
            raise _refuse(error) from error
        return {"id": conversation_id, "events": events}

    app.include_router(router)


__all__ = ["dump_yaml", "install_admin"]
