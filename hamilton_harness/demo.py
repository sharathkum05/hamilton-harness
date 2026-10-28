"""Run several packs at once from clean copies, for showing the harness to people.

`hamilton-harness demo` copies each pack into a scratch folder, starts one
server per pack on consecutive ports, and prints where everything is. Edits
made in the dashboard during a demo land in the copies, so the packs in the
repository are never touched, and the next run starts clean.
"""

from __future__ import annotations

import asyncio
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from hamilton_harness.llm import AnthropicModel, Model
from hamilton_harness.memory import FileStore
from hamilton_harness.pack import Pack, PackError, load_pack
from hamilton_harness.records import FileRecordStore
from hamilton_harness.runtime import Agent
from hamilton_harness.standin import offline_model
from hamilton_harness.web.auth import AdminLogin, Credentials, sign_in_hint

# Written into every folder a demo creates. A folder without it is never deleted.
MARKER = ".hamilton-demo"


@dataclass
class DemoSite:
    name: str
    pack: Pack
    folder: Path
    port: int

    @property
    def pack_dir(self) -> Path:
        return self.folder / "pack"


def find_packs(base: Path) -> list[Path]:
    """Every pack directly under `base`, in name order."""
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if (p / "persona.yaml").is_file())


def _clear(folder: Path) -> None:
    if not folder.exists():
        return
    if not (folder / MARKER).is_file():
        raise PackError(
            f"{folder} exists but was not made by a demo, so it was left alone. "
            "Choose another --state folder."
        )
    shutil.rmtree(folder)


def prepare(packs: list[Path], state: Path, *, first_port: int, keep: bool) -> list[DemoSite]:
    """Copy each pack into its own folder under `state`, fresh unless `keep`."""
    if not packs:
        raise PackError("no packs to show: name a pack folder, or run this where ./packs exists")
    names = [Path(p).resolve().name for p in packs]
    if len(set(names)) != len(names):
        raise PackError(f"two packs share a folder name: {sorted(names)}")

    sites = []
    for offset, (source, name) in enumerate(zip(packs, names, strict=True)):
        source = Path(source).resolve()
        load_pack(source)  # fail on a broken pack before anything is copied or deleted
        folder = state / name
        if not keep:
            _clear(folder)
        if not (folder / "pack").is_dir():
            folder.mkdir(parents=True, exist_ok=True)
            (folder / MARKER).write_text("made by hamilton-harness demo\n", encoding="utf-8")
            shutil.copytree(
                source, folder / "pack", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        sites.append(DemoSite(name, load_pack(folder / "pack"), folder, first_port + offset))
    return sites


def build_app(
    site: DemoSite, *, live: bool, admin_token: str, credentials: Credentials | None = None
) -> FastAPI:
    from hamilton_harness.web.app import create_app

    model: Model = AnthropicModel(site.pack.model) if live else offline_model(site.pack)
    agent = Agent(
        site.pack,
        model,
        store=FileStore(site.folder / "customers"),
        records=FileRecordStore(site.folder / "records.json"),
        trace_dir=site.folder / "traces",
    )
    return create_app(agent, debug=True, admin_token=admin_token, admin_credentials=credentials)


def busy_ports(host: str, ports: list[int]) -> list[int]:
    """The ports in the list that something else is already listening on."""
    busy = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                busy.append(port)
    return busy


def describe(
    sites: list[DemoSite],
    *,
    host: str,
    live: bool,
    admin_token: str,
    login: AdminLogin | None = None,
) -> str:
    """What to print once the servers are up: every rep, and where to find each page."""
    mode = "the real model" if live else "a stand-in for the model, no API key"
    rows = [
        (site.pack.persona.company, f"{site.pack.persona.name}, {site.pack.persona.role}", site)
        for site in sites
    ]
    company_width = max(len(company) for company, _, _ in rows)
    rep_width = max(len(rep) for _, rep, _ in rows)
    lines = [f"Hamilton demo: {len(sites)} rep{'s' if len(sites) != 1 else ''}, using {mode}.", ""]
    for company, rep, site in rows:
        lines.append(f"  {company:<{company_width}}  {rep:<{rep_width}}  http://{host}:{site.port}")
    lines += [
        "",
        "On each address:",
        "  /          the product page",
        "  /demo      the chat with an inspector showing each turn from the inside",
        "  /example   a plain website with the chat embedded by one line",
        "  /admin     the dashboard",
        "",
    ]
    if login is not None:
        # Cookies are kept per host, not per port, so one sign-in covers every rep here.
        lines += [f"Dashboard: {sign_in_hint(login)}", ""]
    lines.append("Dashboards, already signed in:" if login else "Dashboards:")
    for company, _, site in rows:
        lines.append(
            f"  {company:<{company_width}}  http://{host}:{site.port}/admin#token={admin_token}"
        )
    lines += [
        "",
        "Dashboard edits go to the copies in the state folder, never to your packs.",
        "Run it again to start clean, or pass --keep to carry on where you left off.",
        "Ctrl-C to stop.",
    ]
    return "\n".join(lines)


async def serve_all(apps: list[tuple[FastAPI, int]], host: str) -> None:
    import uvicorn

    servers = [
        uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
        for app, port in apps
    ]
    await asyncio.gather(*(server.serve() for server in servers))
