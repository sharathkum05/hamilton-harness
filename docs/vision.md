# Vision

## In one line

Hamilton Harness is a visual builder for the harness around an AI agent. You
drag in what the agent knows, what it may do and what it must never say, test
it against fake customers, and put it live with a click.

## The problem

Putting a language model in front of customers takes more than a prompt. The
agent needs knowledge to answer from, actions it can take, limits on those
actions, a point where a person takes over, tests, and somewhere to run. All of
that together is the harness.

Today a harness is written as code, with an agent framework and a deployment
pipeline around it. That has two costs:

- **Only engineers can build or change it.** The person who knows the refund
  policy cannot edit the thing that enforces it.
- **Getting it live is a project.** Hosting, secrets, storage and a way to roll
  back all have to be wired up before the first customer says hello.

## What Hamilton is

Three promises.

### 1. You build it by dragging, not by writing code

The harness is laid out on a canvas as the path a message takes: the customer
writes, the checks run, the model drafts, the guard decides, the reply goes
out. You build an agent by dragging blocks onto that path:

- **Knowledge**: files, pages and FAQs the agent answers from.
- **Actions**: look up an order, book a slot, take down a quote.
- **Rules**: a refund limit, a phrase it must never say, a subject it stays off.
- **Handoff**: when a person takes over, and what the agent says as it does.
- **Tests**: fake customers, including hostile ones, and what must happen.

Click a block to edit it. Send a message and watch it travel the path, with
each check lighting up as it passes or stops something.

### 2. It is safe by construction

On a free-form canvas you can draw anything, including a path that goes around
the check. Hamilton's canvas does not allow that. The order of the stages is
fixed, so every action and every reply passes the guard, whatever was dragged
where. Rules are enforced in code, not left to the prompt:

> A prompt asks. Code enforces.

And nothing goes live untested. The fake customers run on every change, and a
change that lets a blocked action through does not ship.

### 3. It is easy to put live

- **Connect GitHub.** The agent is a folder of plain files in your own
  repository. Every change on the canvas is a commit, so there is a history,
  a diff to review and a way back. The fake customers run on each one.
- **Connect Vercel.** One click turns that repository into a running agent
  with its own address.
- **Paste one tag.** The chat appears on your website: plain HTML, PHP,
  WordPress or React.
- **Connect your systems.** Drag in a connector and the agent can use it as an
  action, inside the same rules as everything else.

## Who it is for

- **The person who runs the business or the support team.** They know the
  policies. They should be able to build and change the agent without asking
  anyone to write code.
- **The engineer beside them.** They get plain files in Git, a diff for every
  change, tests in CI and a place to add custom actions in code.

It starts with one kind of agent, because that is where a broken rule costs
real money: the company rep that handles support, sales, orders and intake.

## Principles

- **The canvas and the files are the same thing.** The canvas is a view of the
  pack, never a second copy that can drift from it.
- **A prompt asks, code enforces.** Anything that must hold is checked in code.
- **Nothing ships untested.** Tests are part of building, not a step after.
- **Say what it does not do.** Every check is documented with its limits.

## Where it stands

The engine under the canvas exists. The canvas and the one-click path to
production do not yet.

| Part | Today |
|---|---|
| The harness: guard, scope, grounding, handoff, memory, tracing | Built and tested |
| Packs: an agent as a folder of plain files | Built, with three demo packs |
| Fake customers and the scorecard | Built, and run in CI |
| Dashboard | Built, as forms: one screen per part of the pack |
| Chat on your website with one tag | Built |
| Claude managing an agent over MCP | Built, and on npm |
| Hosted demo on Vercel | Built, with a read-only dashboard. It keeps nothing between restarts |
| **The canvas: build the harness by dragging blocks** | Partly. The Flow screen draws the path, each block opens its settings; there is no dragging yet |
| **Watching a message travel the path, live** | Built: a test message on the Flow screen marks each stage passed or stopped |
| **Connect GitHub: every change a commit** | Not built |
| **One-click deploy to Vercel, with storage that persists** | Not built |
| **Connectors as drag-in actions** | Partly. Calls to a web API are set up on the Tools screen with no code; ready-made connectors are not built |
| **Templates to start from** | Partly. `studio` and its setup build a rep from blank; there is one starter |
| A run against the real model | Not done. Tests use scripted and stand-in models |
