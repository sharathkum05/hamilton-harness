## What this changes

<!-- One or two sentences. What can a business or a pack author do now that they could not before, or what no longer goes wrong? -->

## How it was checked

<!-- Tick what you ran. -->

- [ ] `ruff check . && ruff format --check .`
- [ ] `pytest -q`
- [ ] `hamilton-harness sim` on every pack
- [ ] `npm --prefix web run build` (if `web/` changed)
- [ ] `npm --prefix packages/cli test` (if `packages/cli/` changed)

## For a change to a check

<!-- Delete this section if the guard, scope gate, handoff rules and shaper are untouched. -->

- [ ] There is a test where the check catches what it should
- [ ] There is a test where a similar, honest message or reply is left alone
- [ ] `docs/guardrails.md` says what the check does and what it does not
