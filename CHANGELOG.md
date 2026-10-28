# Changelog

What changed, newest first. Version numbers are those of the `hamilton-harness`
package on npm; the Python package in this repository is installed from source
and is not published separately yet.

## Unreleased

### Added

- The dashboard's Flow screen draws the harness as the path a message takes,
  with how each stage is set up. A test message runs one turn and marks every
  stage as passed, stopped or not reached.
- Tools that call a company's web API, set up on the dashboard's Tools screen
  with no code. Secrets come from `TOOL_` environment variables, calls go only
  to public addresses and never follow redirects. Any tool can be tried from
  the dashboard.
- The hosted demo's dashboard is open to anyone, read-only. Each visitor sees
  only the chats and orders they made; saving is refused.
- The demo page's "Things to try" come from the rep's own fake customers and
  openers, so a new rep gets suggestions of its own.
- `HAMILTON_DATABASE_URL` keeps a served rep's orders, customer memory and
  conversations in Postgres, such as Supabase, instead of the state folder.
  Tables go in their own `hamilton` schema, off Supabase's public API, and
  several reps can share one database. Install with `pip install
  "hamilton-harness[db]"`. See docs/supabase.md.
- `hamilton-harness studio [DIR]` builds a rep for your own business from
  blank. It opens the dashboard on a four-step setup (business, knowledge,
  voice, look) that ends with a live chat and the embed line. Setup can be run
  again from the sidebar.
- The dashboard has a sign-in screen: an admin email and password, set with
  `HAMILTON_ADMIN_EMAIL` and `HAMILTON_ADMIN_PASSWORD` or made as a demo login
  and printed when the server starts. Passwords are hashed with scrypt, the
  session is an HttpOnly, SameSite=Strict cookie, and repeated wrong passwords
  lock an address out for a while. The admin token still works.
- The product page header links to the dashboard.
- `hamilton-harness demo` runs every pack in `./packs` at once, one per port,
  from clean copies, and prints each rep's address and dashboard link.
  Dashboard edits made during a demo never touch the packs themselves.
- `serve --offline` works for any pack. A pack without its own stand-in model
  gets one that answers from its notes.
- `/example`: a plain example website with the chat embedded by one line.
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
- The lettings pack has a stand-in model, so the intake chat and its inbox can
  be run with `serve --offline` and no API key.
- The dashboard's Tests screen and the `run_fake_customers` MCP tool report
  pack warnings alongside the scorecard.
- Guides: [writing a pack](docs/packs.md), [how the guardrails
  work](docs/guardrails.md) and [fake customers](docs/scenarios.md).
- A contributing guide, a security policy, issue forms and a pull request
  checklist.

### Fixed

- The offline stand-in now picks up dashboard edits, such as a new disclosure
  line, instead of the lines the pack had when the server started.

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
- Strict mode turned away questions that said when: "can I see the studio
  tomorrow morning" was refused because "tomorrow" and "morning" appear in no
  note. Words that only say when are no longer counted.
- A company with no logo had an empty box in the dashboard header. It now
  shows the company's initial.

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
