# Contributing

Thanks for taking a look. Bug reports, new packs, new checks and documentation
fixes are all welcome.

## Set up

You need Python 3.11 or newer and Node 22.

```bash
pip install -e ".[dev]"
```

```bash
npm --prefix web ci
```

```bash
npm --prefix packages/cli ci
```

None of the tests need an API key. They run against scripted models.

## Before you open a pull request

These are the same checks CI runs.

```bash
ruff check . && ruff format --check .
```

```bash
pytest -q
```

```bash
for pack in packs/*/; do hamilton-harness sim "$pack" || break; done
```

```bash
npm --prefix web run format:check && npm --prefix web run build
```

```bash
npm --prefix packages/cli test
```

## What a good change looks like

- **Small commits, each of which says what it does.** "Stop the rep quoting a
  bulk price" is a better subject than "fix guard".
- **A test for anything enforced in code.** If you change the guard, the scope
  gate, the handoff rules or the shaper, add a unit test. If the change is
  visible in a conversation, add a fake customer to a pack as well.
- **A test for the false positive, not only the catch.** A check that stops a
  bad reply must also leave a similar honest reply alone. Test both.
- **Plain claims in the docs.** Say what a check does and what it does not. If
  something has only been run against a scripted model, say so.

## Adding a pack

Start from the scaffold:

```bash
hamilton-harness init packs/your-company --company "Your Company"
```

Then follow [docs/packs.md](docs/packs.md). A pack in this repository should:

- describe a made-up company, with no real customer data;
- have a fake customer for every rule that is enforced in code, where the
  recorded model breaks the rule and the harness stops it
  ([docs/scenarios.md](docs/scenarios.md));
- be added to the simulator step in `.github/workflows/ci.yml`.

## Adding or changing a check

The checks and the order they run in are described in
[docs/guardrails.md](docs/guardrails.md). Two rules of thumb:

- A check belongs in code only if it can be decided without a model. Anything
  that needs judgement belongs in the prompt and in the fake customers.
- A check that cannot evaluate something should refuse, not allow. A refund
  limit that cannot read the amount blocks the refund.

Update `docs/guardrails.md` in the same pull request, including the "what it
does not do" part.

## Where things are

The README has a table of every module under "Project layout". The web app is
in `web/`, and its vendored components and their licences are listed in
`web/THIRD_PARTY.md`. Components under `web/src/components/ui` come from
shadcn/ui, ElevenLabs UI and Magic UI; prefer adding an official component over
writing a new one by hand.

## Reporting a security problem

Please do not open a public issue. See [SECURITY.md](SECURITY.md).
