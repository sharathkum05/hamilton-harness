"""The dashboard's API: read and edit the pack that is being served.

Every route needs the admin token. An edit is validated, written to the pack's
own YAML or Markdown file, and the pack is reloaded. If the edited pack no
longer loads, the file is put back and the edit is refused, so a bad save can
never take the rep offline.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from repkit.pack import PackError
from repkit.pack.schema import HandoffRules, Persona, PolicyRule, ScopeSettings, WidgetSettings
from repkit.sim import load_scenarios, run_scenarios
from repkit.trace import read_trace

# Sections stored as one YAML mapping each.
SECTIONS: dict[str, type[BaseModel]] = {
    "persona": Persona,
    "scope": ScopeSettings,
    "widget": WidgetSettings,
    "handoff": HandoffRules,
}

MAX_LOGO_BYTES = 512_000
MAX_KNOWLEDGE_CHARS = 200_000
LOGO_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}
_KNOWLEDGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,60}\.md")
_TRACE_ID = re.compile(r"[0-9a-f]{12}")
_UNSAFE_SVG = re.compile(rb"<script|javascript:|\son\w+\s*=|<foreignObject", re.IGNORECASE)


class KnowledgeText(BaseModel):
    text: str = Field(max_length=MAX_KNOWLEDGE_CHARS)


def _problems(error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in item['loc']) or 'value'}: {item['msg']}"
        for item in error.errors()
    )


def _dump(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88)


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


def _summarise(conversation_id: str, records: list[dict[str, Any]], modified: float) -> dict:
    first = next((r.get("text", "") for r in records if r["kind"] == "customer"), "")
    return {
        "id": conversation_id,
        "turns": max((r.get("turn", 0) for r in records), default=0),
        "updated_at": modified,
        "opening": first[:140],
        "handed_off": any(r["kind"] == "handoff" for r in records),
        "blocked": any(
            r["kind"] == "reply_blocked"
            or (r["kind"] == "action" and r.get("outcome") == "blocked")
            for r in records
        ),
        "refused": any(r["kind"] == "scope_refused" for r in records),
    }


def install_admin(app: FastAPI, holder: Any, token: str) -> None:
    """Add the dashboard routes to `app`, guarded by `token`."""

    def require_admin(authorization: str | None = Header(default=None)) -> None:
        supplied = (authorization or "").removeprefix("Bearer ").strip()
        # compare_digest: the time taken must not reveal how much of the token matched.
        if not supplied or not secrets.compare_digest(supplied.encode(), token.encode()):
            raise HTTPException(status_code=401, detail="admin token required")

    router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

    def root() -> Path:
        return Path(holder.pack.root)

    def save(path: Path, content: str | bytes | None) -> None:
        """Write (or delete, when content is None) one pack file, then reload.

        A pack that no longer loads is rolled back to what was there before.
        """
        previous = path.read_bytes() if path.exists() else None
        path.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            path.unlink(missing_ok=True)
        elif isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        try:
            holder.reload()
        except PackError as error:
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/pack")
    def get_pack() -> dict[str, Any]:
        pack = holder.pack
        try:
            scenarios = len(load_scenarios(pack))
        except PackError:
            scenarios = 0
        return {
            "persona": pack.persona.model_dump(mode="json"),
            "scope": pack.scope.model_dump(mode="json"),
            "widget": pack.widget.model_dump(mode="json"),
            "handoff": pack.handoff.model_dump(mode="json"),
            "model": pack.model.model_dump(mode="json"),
            "policies": [rule.model_dump(mode="json") for rule in pack.policies],
            "tools": [
                {
                    "name": t.name,
                    "description": " ".join(t.description.split()),
                    "handler": t.handler,
                }
                for t in pack.tools
            ],
            "knowledge": [doc.model_dump() for doc in pack.knowledge],
            "examples": [chat.model_dump() for chat in pack.examples],
            "scenarios": scenarios,
        }

    @router.put("/pack/policies")
    def put_policies(rules: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            validated = [PolicyRule.model_validate(rule) for rule in rules]
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=_problems(error)) from error
        data = {
            "policies": [rule.model_dump(mode="json", exclude_defaults=True) for rule in validated]
        }
        save(root() / "policies.yaml", _dump(data))
        return {"saved": "policies", "count": len(validated)}

    @router.put("/pack/{section}")
    def put_section(section: str, values: dict[str, Any]) -> dict[str, Any]:
        model = SECTIONS.get(section)
        if model is None:
            raise HTTPException(status_code=404, detail=f"no editable section '{section}'")
        try:
            validated = model.model_validate(values)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=_problems(error)) from error
        save(root() / f"{section}.yaml", _dump(validated.model_dump(mode="json")))
        return {"saved": section}

    @router.put("/knowledge/{name}")
    def put_knowledge(name: str, body: KnowledgeText) -> dict[str, Any]:
        if not _KNOWLEDGE_NAME.fullmatch(name):
            raise HTTPException(status_code=422, detail="file name must look like shipping.md")
        save(root() / "knowledge" / name, body.text)
        return {"saved": name}

    @router.delete("/knowledge/{name}")
    def delete_knowledge(name: str) -> dict[str, Any]:
        if not _KNOWLEDGE_NAME.fullmatch(name):
            raise HTTPException(status_code=422, detail="file name must look like shipping.md")
        path = root() / "knowledge" / name
        if not path.exists():
            raise HTTPException(status_code=404, detail="no such knowledge file")
        save(path, None)
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

        brand = root() / "brand"
        brand.mkdir(exist_ok=True)
        for old in brand.glob("logo.*"):
            old.unlink()
        (brand / f"logo.{extension}").write_bytes(data)
        settings = holder.pack.widget.model_copy(update={"logo": f"brand/logo.{extension}"})
        save(root() / "widget.yaml", _dump(settings.model_dump(mode="json")))
        return {"saved": settings.logo}

    @router.delete("/logo")
    def delete_logo() -> dict[str, Any]:
        for old in (root() / "brand").glob("logo.*"):
            old.unlink()
        settings = holder.pack.widget.model_copy(update={"logo": ""})
        save(root() / "widget.yaml", _dump(settings.model_dump(mode="json")))
        return {"deleted": "logo"}

    @router.post("/sim")
    def run_sim() -> dict[str, Any]:
        pack = holder.pack
        try:
            scenarios = load_scenarios(pack)
        except PackError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        scorecard = run_scenarios(pack, scenarios, model_name="replay")
        return {
            "summary": scorecard.summary(),
            "results": [
                {
                    "id": result.scenario.id,
                    "customer": result.scenario.customer,
                    "says": result.scenario.says,
                    "passed": result.passed,
                    "replies": [turn.text for turn in result.turns],
                    "failures": [
                        {"name": check.name, "detail": check.detail} for check in result.failures
                    ],
                    "error": result.error,
                }
                for result in scorecard.results
            ],
        }

    @router.get("/conversations")
    def list_conversations() -> dict[str, Any]:
        directory = holder.agent.trace_dir
        if directory is None or not directory.is_dir():
            return {"conversations": []}
        files = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        return {
            "conversations": [
                _summarise(path.stem, read_trace(path), path.stat().st_mtime) for path in files[:50]
            ]
        }

    @router.get("/conversations/{conversation_id}")
    def get_conversation(conversation_id: str) -> dict[str, Any]:
        directory = holder.agent.trace_dir
        if directory is None or not _TRACE_ID.fullmatch(conversation_id):
            raise HTTPException(status_code=404, detail="conversation not found")
        path = directory / f"{conversation_id}.jsonl"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="conversation not found")
        return {"id": conversation_id, "events": read_trace(path)}

    app.include_router(router)
