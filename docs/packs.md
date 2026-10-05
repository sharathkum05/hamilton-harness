# Writing a pack

A pack is a folder of YAML and Markdown that describes one company's rep. It is
the only thing that changes between companies: the harness code is the same for
a shoe shop, a dental practice and a lettings agency.

Start from a working one:

```bash
hamilton-harness init packs/acme --company "Acme Tools" --rep Jo
```

```bash
hamilton-harness validate packs/acme
```

`validate` loads the pack, resolves every handler and reports the first thing
that is wrong. Unknown keys are errors, because in a hand-edited file they are
almost always typos.

A pack can load and still work against itself, so `validate` also lists
warnings:

```
2 things worth a second look:
  handoff.yaml: message: contains the banned phrase "Kindly", which is cut before sending
  policies.yaml: no-discounts: has never_say patterns but no fake customer expects replaced_by: no-discounts
```

| Warning | What it means |
|---|---|
| A line breaks a rule | A greeting, handoff message, off-topic line or `safe_reply` matches a `never_say` pattern, or claims to be a person |
| A line has a banned phrase | One of those lines contains a phrase from `banned_phrases`. The shaper cuts it from anything sent as a reply; a greeting is shown as written, banned phrase and all |
| A line is too long | A line sent as a reply runs past three bubbles of `max_sentences`, so its end is never sent |
| An example breaks a rule | A `rep:` line in an example chat says something a rule forbids. The model copies its examples |
| A rule is untested | A rule with `limits`, `forbid` or `never_say` has no fake customer that proves it holds |
| No scope, or no scenarios | `covers` is empty, or the pack has no `tests/scenarios.yaml` |

Add `--strict` to make any warning a failure, which is how this repository's
CI runs it.

## The files

| File | Required | What it holds |
|---|---|---|
| `persona.yaml` | yes | Who the rep is and how they talk |
| `examples/*.md` | no | Real chats by the company's own reps |
| `knowledge/*.md` | no | Products, prices, hours, FAQs |
| `policies.yaml` | no | What the rep may promise and do |
| `tools.yaml`, `handlers.py` | no | Actions in the company's systems |
| `records.yaml` | no | Things the rep takes down: orders, quotes, applications |
| `scope.yaml` | no | What the rep is for and what it turns away |
| `handoff.yaml` | no | When a human takes over |
| `widget.yaml` | no | How the web chat looks |
| `model.yaml` | no | Which model, and how hard it thinks |
| `tests/scenarios.yaml` | no | Fake customers, covered in [scenarios.md](scenarios.md) |
| `offline_model.py` | no | A stand-in model for demos with no API key |

## persona.yaml

```yaml
name: Maya
company: Loop Sneakers
role: customer support
voice:
  - casual and warm, like texting a friend who works at the shop
  - says what you did, then what happens next
language: English
max_sentences: 2
emoji: true
banned_phrases:
  - I apologize for the inconvenience
disclosure: I'm Maya, Loop's AI assistant. I can get a person on the line any time you want.
notes: ""
```

| Field | Default | Meaning |
|---|---|---|
| `name`, `company` | required | Used in the system prompt and the chat header |
| `role` | `customer support` | The job, in a few words |
| `voice` | none | One line per trait. Concrete lines work better than adjectives |
| `language` | `English` | The language replies are written in |
| `max_sentences` | `3` | Sentences per chat bubble. A reply is split into bubbles of this size and anything past the third bubble is dropped, in code |
| `emoji` | `false` | Whether the rep may use one. When `false`, any the model writes are removed |
| `banned_phrases` | none | Cut out of a reply before it is sent. A sentence left with fewer than three words is dropped |
| `disclosure` | `I'm an AI assistant.` | Said when a customer asks whether they are talking to an AI, and sent in place of any draft that claims to be a person |
| `notes` | empty | Anything else about the company the rep should always know |

## examples/

One file per conversation. Lines start with `customer:` or `rep:`. A line with
no speaker continues the previous turn, and a line starting with `#` is a
comment.

```
# Booking a check-up, one question at a time.
customer: hi can I get a check-up this week
rep: Of course. I have Thursday at 10:00 am or Friday at 4:30 pm. Which suits you?
```

The examples go into the system prompt and the model matches their tone and
length. Three good ones do more for the voice than a page of description.

## knowledge/

Markdown files. Each heading becomes one note, and for every customer message
the three best-matching notes are given to the model. So:

- Keep one subject per heading.
- Write in the words customers use. A note that says "You can book a viewing
  here" is found by "can I book a viewing"; one that says "Viewing requests are
  accepted" may not be.
- Put every price, date and time limit the rep may state in a note. With
  `ground_numbers` on, a figure that appears in no note, rule or tool result is
  treated as invented and the reply is replaced.

Lookup is BM25 over words, with plurals and spelled-out numbers folded, so
"two bedrooms" finds "2 bedroom". There is no embedding service to run.

## policies.yaml

```yaml
policies:
  - id: refund-limit
    text: You can refund up to ₹3,000 on an order yourself. Anything above that goes to a human.
    tool: issue_refund
    limits:
      - field: amount_inr
        max: 3000
    on_violation: handoff
    topics: [refund, money back, charged]
```

| Field | Meaning |
|---|---|
| `id` | A short name. It appears in traces and scenario results |
| `text` | Shown to the model. Write it the way you would brief a new hire |
| `topics` | Words that make the rule relevant to a message. A rule with no topics is shown on every turn |
| `tool` | The action this rule constrains |
| `limits` | Bounds on that action's arguments: `max`, `min` or `allowed` values for a `field` |
| `forbid` | `true` refuses the action whatever its arguments |
| `on_violation` | `block` refuses the action and tells the model why. `handoff` passes the conversation to a person |
| `never_say` | Regular expressions a reply must never match, checked without regard to case |
| `safe_reply` | Sent in place of a reply that matched `never_say` |

`text` and `topics` only inform the model. `limits`, `forbid` and `never_say`
are checked in code and hold whatever the model writes. A rule with limits must
name a `tool`, and that tool must exist.

Two things to get right when you write a `never_say` pattern:

- The rule's own `safe_reply` must not match it. `validate` warns when it does.
- An honest sentence must not match it. "You're approved" should be caught;
  "they'll tell you if you're approved" should not. The lettings pack shows how
  to tell them apart with lookbehinds.

## tools.yaml and handlers.py

```yaml
tools:
  - name: find_slots
    description: List the next free appointment slots for a treatment.
    handler: handlers:find_slots
    input_schema:
      type: object
      properties:
        treatment: {type: string, enum: [checkup, filling]}
      required: [treatment]
      additionalProperties: false
    remember:
      name: patient_name
```

`handler` is `module:function`, resolved inside the pack folder. `input_schema`
is JSON Schema; arguments are validated against it before any rule is checked.
`remember` names facts to keep about the customer after a successful call, as
`fact name: field in the result`.

A handler is an ordinary Python function that returns something JSON can hold:

```python
def find_slots(treatment: str) -> dict:
    free = [slot for slot in SLOTS if slot["free"]]
    if not free:
        raise LookupError("There are no free appointments this week.")
    return {"treatment": treatment, "slots": free}
```

Raise `LookupError` or `ValueError` for something the rep can explain to the
customer; the message is passed to the model. Any other exception is logged and
the model is told only that the system is not responding.

## records.yaml

A record type is something the rep takes down for the business. Each one
becomes an action named `create_<name>`, with a schema built from its fields.

```yaml
records:
  - name: quote
    label: Quote request
    description: Take a quotation request for a bulk order of six pairs or more.
    fields:
      - name: product
        type: choice
        choices: [Drift Runner, Court Classic, Trail Loop]
      - name: quantity
        type: number
      - name: customer_name
      - name: notes
        required: false
```

A field's `type` is `text` (the default), `number` or `choice`. Every field is
required unless it says otherwise. The customer is given a reference made from
the first three letters of the name and a number, such as `QUO-0001`, and the
record appears in the dashboard inbox. Rules can constrain a record's action
like any other, by naming `create_quote` as their `tool`.

## scope.yaml

```yaml
covers: >
  Brightside Dental only: booking, moving and cancelling appointments, the
  treatments the practice offers and what they cost.
off_topic_reply: I can only help with Brightside Dental. What do you need?
unsure_reply: I don't have that in front of me and I don't want to guess.
refuse: [math, coding, writing, trivia]
also_refuse: []
strict: true
ground_numbers: true
```

| Field | Default | Meaning |
|---|---|---|
| `covers` | empty | Shown to the model: the subjects this rep helps with |
| `off_topic_reply` | a generic line | Sent when a message is turned away |
| `unsure_reply` | a generic line | Sent in place of a reply that states an invented figure |
| `refuse` | all four | Kinds of request turned away in code, before the model is called |
| `also_refuse` | none | Extra regular expressions that mark a message as off topic |
| `strict` | `false` | Turn away any message that touches nothing in the pack |
| `ground_numbers` | `true` | Replace replies that state a number found in no source |

What each of these does, and what it does not, is in
[guardrails.md](guardrails.md).

## handoff.yaml

```yaml
phrases: [emergency, severe pain]
on_request: true
max_guard_blocks: 2
message: I'm passing you to our front desk team right now.
```

`phrases` hand the conversation over at once, before the model is called.
`on_request` does the same when the customer asks for a person.
`max_guard_blocks` counts blocked actions and replaced replies in one
conversation, and hands over when the rep next tries an action with the count
at or past this number. After a handoff the rep stays out of the conversation.

## widget.yaml

| Field | Default | Meaning |
|---|---|---|
| `greeting` | `Hi! How can I help?` | The first message in the chat |
| `launcher_label` | `Chat with us` | The label on the launcher button |
| `accent` | `auto` | `auto` (black on light, white on dark) or a six-digit hex colour |
| `suggestions` | none | Up to four one-tap openers |
| `title` | the rep's name | The heading of the chat panel |
| `logo` | none | A png, jpg, webp or svg inside the pack, such as `brand/logo.svg` |
| `theme` | `auto` | `auto`, `light` or `dark` |
| `position` | `right` | `right` or `left` |
| `corners` | `soft` | `sharp`, `soft` or `round` |
| `font` | `system` | `system`, `serif`, `rounded` or `mono` |
| `header` | `plain` | `plain`, or `accent` to fill the header with the brand colour |

All of these can be edited from the dashboard's Brand screen.

## model.yaml

```yaml
name: claude-opus-5-5
effort: low
max_tokens: 16000
```

`effort` is one of `low`, `medium`, `high`, `xhigh` or `max`. A support chat
wants short, quick replies, so the default is `low`.

## offline_model.py

Optional. A module with a `build()` function that returns a model, used by
`hamilton-harness serve --offline` so the chat can be shown with no API key.
The Loop Sneakers pack has one. It is a stand-in for demos: it pattern-matches
a handful of messages and is not a measure of how the real model behaves.

## Editing a pack once it is running

Three ways:

- Edit the files, run `hamilton-harness validate`, and restart the server.
- Use the dashboard at `/admin`.
- Connect Claude over MCP and ask it to make the change. See the README's
  "Connect Claude" section.

The dashboard and Claude both go through the same editor, which validates
every change and rolls it back if the pack would no longer load.
