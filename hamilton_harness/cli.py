"""Command line entry point.

hamilton-harness init DIR           write a starter pack for a new company
hamilton-harness validate PACK      check a pack loads and its handlers resolve
hamilton-harness chat PACK          talk to the rep in the terminal
hamilton-harness sim PACK           run the pack's fake customers and print a scorecard
hamilton-harness serve PACK         run the web chat widget and its API
hamilton-harness mcp PACK           let Claude manage the pack over MCP
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path

from hamilton_harness.llm import AnthropicModel, Model, ModelError, load_offline_model
from hamilton_harness.memory import FileStore
from hamilton_harness.pack import PackError, load_pack
from hamilton_harness.pack.schema import Pack
from hamilton_harness.records import FileRecordStore
from hamilton_harness.runtime import Agent, TurnResult
from hamilton_harness.scaffold import write_starter_pack
from hamilton_harness.sim import load_scenarios, replay_model, run_scenarios
from hamilton_harness.tools import ToolError, ToolRegistry


def _live_model(pack: Pack) -> Model:
    return AnthropicModel(pack.model)


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.dir)
    written = write_starter_pack(root, company=args.company, rep=args.rep)
    load_pack(root)  # a starter that does not load is a bug here, not the user's problem
    print(f"Wrote a starter pack for {args.company.strip()} to {root}")
    for path in written:
        print(f"  {path.relative_to(root)}")
    print("\nNext, run its fake customers. No API key is needed:")
    print(f"  hamilton-harness sim {root}")
    print("Then, with ANTHROPIC_API_KEY set, open the chat widget and the dashboard:")
    print(f"  hamilton-harness serve {root} --admin")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    pack = load_pack(args.pack)
    registry = ToolRegistry(pack)
    enforced = [r for r in pack.policies if r.tool or r.never_say]
    print(f"{pack.persona.name} at {pack.persona.company} ({pack.persona.role})")
    print(f"  examples   {len(pack.examples)}")
    print(f"  knowledge  {len(pack.knowledge)} files")
    print(f"  tools      {', '.join(registry.names()) or 'none'}")
    print(f"  rules      {len(pack.policies)} ({len(enforced)} enforced in code)")
    try:
        print(f"  scenarios  {len(load_scenarios(pack))}")
    except PackError:
        print("  scenarios  none")
    print("Pack is valid.")
    return 0


def _print_turn(result: TurnResult, name: str, *, pacing: bool, debug: bool) -> None:
    if debug:
        for action in result.actions:
            rules = f" {list(action.rule_ids)}" if action.rule_ids else ""
            print(f"  · {action.tool} {json.dumps(action.arguments)} -> {action.outcome}{rules}")
        if result.replaced_by:
            print(f"  · draft replaced by rule {result.replaced_by}")
        if result.refused:
            print(f"  · turned away as off topic ({result.refused}), model not called")
    for bubble in result.bubbles:
        if pacing:
            time.sleep(bubble.delay)
        print(f"{name}: {bubble.text}")
    if result.handoff:
        print(f"  [handed to a human: {result.handoff.reason}, {result.handoff.detail}]")


def cmd_chat(args: argparse.Namespace) -> int:
    pack = load_pack(args.pack)
    store = FileStore(Path(args.state) / "customers")
    agent = Agent(pack, _live_model(pack), store=store, trace_dir=Path(args.state) / "traces")
    conversation = agent.start(args.customer)
    print(f"Chatting with {pack.persona.name} at {pack.persona.company}. Ctrl-D to leave.\n")
    while True:
        try:
            message = input("you: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue
        result = agent.respond(conversation, message)
        _print_turn(result, pack.persona.name.lower(), pacing=not args.no_pacing, debug=args.debug)
    print(f"Trace: {Path(args.state) / 'traces' / (conversation.id + '.jsonl')}")
    return 0


def cmd_sim(args: argparse.Namespace) -> int:
    pack = load_pack(args.pack)
    scenarios = load_scenarios(pack, args.scenarios)
    if args.only:
        scenarios = [s for s in scenarios if s.id in args.only]
        if not scenarios:
            raise PackError(f"no scenario matches {args.only}")
    if args.live:
        model = _live_model(pack)
        scorecard = run_scenarios(pack, scenarios, lambda _: model, model_name=model.name)
    else:
        scorecard = run_scenarios(pack, scenarios, replay_model, model_name="replay")
    if args.json:
        failures = {r.scenario.id: [c.name for c in r.failures] for r in scorecard.results}
        print(json.dumps({"summary": scorecard.summary(), "failures": failures}, indent=2))
    else:
        print(f"mode: {'live ' + scorecard.model if args.live else 'replay'}\n")
        print(scorecard.render())
    return 0 if scorecard.ok else 1


def admin_token(state: Path) -> str:
    """The dashboard's token: from the environment, or made once and kept in the state folder."""
    from_env = os.environ.get("HAMILTON_ADMIN_TOKEN", "").strip()
    if from_env:
        return from_env
    path = state / "admin-token"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    state.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    path.write_text(token, encoding="utf-8")
    path.chmod(0o600)
    return token


def build_web_app(args: argparse.Namespace):
    """The web app for `serve`, built separately so it can be tested without a server."""
    from hamilton_harness.web.app import create_app

    pack = load_pack(args.pack)
    model = load_offline_model(pack.root) if args.offline else _live_model(pack)
    state = Path(args.state)
    agent = Agent(
        pack,
        model,
        store=FileStore(state / "customers"),
        records=FileRecordStore(state / "records.json"),
        trace_dir=state / "traces",
    )
    return create_app(
        agent,
        debug=args.debug,
        allow_origins=args.allow_origin or (),
        admin_token=admin_token(state) if args.admin else None,
        identity_secret=os.environ.get("HAMILTON_IDENTITY_SECRET") or None,
    )


def cmd_serve(args: argparse.Namespace) -> int:
    app = build_web_app(args)
    import uvicorn

    mode = "offline stand-in model" if args.offline else "live model"
    print(f"Serving the chat widget at http://{args.host}:{args.port} ({mode})", flush=True)
    if args.admin:
        # The token rides in the URL fragment, which browsers never send to a server.
        token = admin_token(Path(args.state))
        print(f"Dashboard: http://{args.host}:{args.port}/admin#token={token}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_mcp(args: argparse.Namespace) -> int:
    try:
        from hamilton_harness.mcp_server import build_server
    except ImportError as exc:
        raise PackError(
            'the MCP server needs an extra package: pip install "hamilton-harness[mcp]"'
        ) from exc

    load_pack(args.pack)  # fail early, with a clear message, on a pack that does not load
    state = Path(args.state)
    build_server(args.pack, trace_dir=state / "traces", records_path=state / "records.json").run(
        "stdio"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hamilton-harness", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="write a starter pack")
    init.add_argument("dir", help="folder to create the pack in")
    init.add_argument("--company", required=True, help="the company the rep works for")
    init.add_argument("--rep", default="Sam", help="the rep's first name")
    init.set_defaults(run=cmd_init)

    validate = commands.add_parser("validate", help="check a pack")
    validate.add_argument("pack")
    validate.set_defaults(run=cmd_validate)

    chat = commands.add_parser("chat", help="talk to the rep")
    chat.add_argument("pack")
    chat.add_argument("--customer", help="customer id, to remember facts between chats")
    chat.add_argument("--state", default=".hamilton", help="where traces and memory are kept")
    chat.add_argument("--no-pacing", action="store_true", help="print replies without delays")
    chat.add_argument("--debug", action="store_true", help="show actions and guard decisions")
    chat.set_defaults(run=cmd_chat)

    sim = commands.add_parser("sim", help="run the pack's fake customers")
    sim.add_argument("pack")
    sim.add_argument("--live", action="store_true", help="use the real model, not the replays")
    sim.add_argument("--scenarios", help="scenario file, if not PACK/tests/scenarios.yaml")
    sim.add_argument("--only", nargs="+", metavar="ID", help="run just these scenarios")
    sim.add_argument("--json", action="store_true", help="print the scorecard as JSON")
    sim.set_defaults(run=cmd_sim)

    serve = commands.add_parser("serve", help="run the web chat widget")
    serve.add_argument("pack")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--offline", action="store_true", help="use the pack's stand-in model")
    serve.add_argument("--debug", action="store_true", help="expose each turn to the inspector")
    serve.add_argument("--state", default=".hamilton", help="where traces and memory are kept")
    serve.add_argument("--admin", action="store_true", help="switch on the dashboard at /admin")
    serve.add_argument(
        "--allow-origin", action="append", metavar="URL", help="site allowed to embed the widget"
    )
    serve.set_defaults(run=cmd_serve)

    mcp = commands.add_parser("mcp", help="let Claude manage the pack over MCP")
    mcp.add_argument("pack")
    mcp.add_argument("--state", default=".hamilton", help="where the server keeps traces")
    mcp.set_defaults(run=cmd_mcp)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.run(args)
    except (PackError, ToolError, ModelError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
