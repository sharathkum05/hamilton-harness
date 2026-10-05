# Changelog

What changed, newest first. Version numbers are those of the `hamilton-harness`
package on npm; the Python package in this repository is installed from source
and is not published separately yet.

## Unreleased

### Added

- `hamilton-harness init DIR --company NAME` writes a starter pack that
  validates and passes its own fake customers.
- `hamilton-harness validate` lists warnings about a pack that loads but works
  against itself: a fixed line or example chat that breaks one of the pack's
  own rules, a line the shaper will cut or truncate, and a code-enforced rule
  that no fake customer tests. `--strict` turns warnings into a failure.
- A third demo pack, **Kestrel Lettings**: application intake for a lettings
  agency. It takes rental applications and viewing requests, and has rules
  against deciding an application, giving legal advice and asking about
  protected characteristics.
- Guides: [writing a pack](docs/packs.md), [how the guardrails
  work](docs/guardrails.md) and [fake customers](docs/scenarios.md).
- A contributing guide, a security policy, issue forms and a pull request
  checklist.

### Fixed

- Notes are now found when the customer uses a plural or spells out a number:
  "two bedrooms" matches a note that says "2 bedroom".
- In a notes file with no top-level heading, sibling `##` sections were nested
  under one another, so one section's words counted towards the next.
- Strict mode turned away ordinary questions when one word was filler. "What
  treatments do you offer" was refused by the dental pack because "offer"
  appears in no note. Words that ask without naming a subject are no longer
  counted.
- Strict mode turned away "am I talking to a bot?" as off topic. It now gets
  the rep's disclosure line.

## 0.1.1 (4 October 2026)

- The npm package carries its MCP Registry name and a `server.json`, and is
  listed in the registry as `io.github.sharathkum05/hamilton-harness`.
- The MCP server reports its version from `package.json`.

## 0.1.0 (4 October 2026)

The first release.

- **The harness.** A turn loop with a policy guard for actions and replies, a
  scope gate, a number grounding check, handoff rules, customer memory, a
  reply shaper and a trace of every turn.
- **Packs.** A company's rep as YAML and Markdown: persona, example chats,
  knowledge, rules, tools, record types, scope, handoff and widget settings.
  Two demo packs, Loop Sneakers and Brightside Dental.
- **Records.** Orders, quotes and other things the rep takes down, each with a
  reference for the customer and an inbox for the business.
- **The simulator.** Fake customers with expected outcomes, replayed with no
  API key, and a scorecard that fails the build.
- **The web app.** A chat panel, an embed script for any website, a dashboard
  for the business and a product page.
- **Claude over MCP.** A local MCP server for a pack, and this npm package:
  `login`, `status`, `mcp` and `logout`, with eleven tools for managing a
  running rep.
