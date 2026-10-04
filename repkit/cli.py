"""Command line entry point.

repkit validate PACK      check a pack loads and its handlers resolve
repkit chat PACK          talk to the rep in the terminal
repkit sim PACK           run the pack's fake customers and print a scorecard
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from repkit.llm import AnthropicModel, Model, ModelError
from repkit.memory import FileStore
from repkit.pack import PackError, load_pack
from repkit.pack.schema import Pack
from repkit.runtime import Agent, TurnResult
from repkit.sim import load_scenarios, replay_model, run_scenarios
from repkit.tools import ToolError, ToolRegistry


def _live_model(pack: Pack) -> Model:
    return AnthropicModel(pack.model)


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repkit", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="check a pack")
    validate.add_argument("pack")
    validate.set_defaults(run=cmd_validate)

    chat = commands.add_parser("chat", help="talk to the rep")
    chat.add_argument("pack")
    chat.add_argument("--customer", help="customer id, to remember facts between chats")
    chat.add_argument("--state", default=".repkit", help="where traces and memory are kept")
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
