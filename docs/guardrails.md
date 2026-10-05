# How the guardrails work

A prompt asks the model to behave. The harness does not rely on asking. Around
every model call there are checks written in ordinary code, and each of them
holds whatever the model wrote.

This page lists them in the order they run in a turn, says what each one
catches, and says what it does not.

## The order of a turn

| Step | Runs | If it fires |
|---|---|---|
| 1. Handoff check | on the customer's message | A person takes over. The model is not called |
| 2. Context lookup | on the customer's message | Nothing fires. It picks the rules and notes for this message |
| 3. Scope gate | on the customer's message | The off-topic line is sent. The model is not called |
| 4. Argument validation | on each action the model proposes | The model is told what is wrong with the arguments |
| 5. Policy guard | on each action the model proposes | The action is refused, or a person takes over |
| 6. Reply guard | on the model's draft reply | The rule's safe reply is sent instead |
| 7. Grounding check | on the model's draft reply | The pack's "not sure" line is sent instead |
| 8. Reply shaper | on whatever is being sent | Formatting, banned phrases and extra length are removed |

Every step writes to the conversation's trace, so any reply can be explained
afterwards: which notes were looked up, what the model drafted, which rule
replaced it and what the customer actually saw.

## 1. Handoff check

Three things hand a conversation to a person before the model sees the message:

- a phrase the pack lists in `handoff.yaml`, such as "emergency";
- the customer asking for a person ("let me talk to a human"), when
  `on_request` is on;
- the conversation having already been handed off. From then on the rep stays
  out of it.

"Are you a real person?" is a question about the rep, not a request for one,
and is not treated as a handoff.

Later in the turn, two more things hand off: a rule whose `on_violation` is
`handoff`, and the count of blocks in the conversation reaching
`max_guard_blocks`. A
model error that a retry does not fix also hands off, because a customer should
never be left with silence.

## 2. Context lookup

For each message the harness picks the rules whose `topics` appear in it, the
three best-matching knowledge notes, and what is remembered about the customer.
They are given to the model with the message. Rules with no topics are in the
system prompt on every turn.

This step refuses nothing. It matters to the checks that follow, because the
scope gate asks whether the pack had anything to say about the message.

## 3. Scope gate

The gate decides whether the rep should engage at all.

**Detectors.** Four kinds of request are recognised by pattern and turned away:
`math`, `coding`, `writing` and `trivia`. A pack chooses which with `refuse`
and adds its own patterns with `also_refuse`. One exception: sums that are
about the company's own prices ("what's two pairs plus shipping?") are let
through, which the gate detects by the message matching a rule or a note.

**Strict mode.** With `strict: true` the gate also turns away any message the
pack has nothing to say about. A message counts as covered when it matches a
rule's topics, or shares enough words with the notes looked up for it: every
word of a one- or two-word question, at least two of a longer one. Words that
ask without naming a subject ("tell", "about", "offer", "still") are not
counted.

Three kinds of message always pass strict mode: greetings and thanks, questions
about the rep itself ("am I talking to a bot?"), and a short answer to a
question the rep just asked. Without the last one, a customer who replies
"Priya Raman" to "what's your name?" would be told that is off topic.

**What it does not do.** The gate is a filter on wording. A message that names
something the notes mention will pass it, and is then handled by the model,
which is told the scope in its prompt. Strict mode also has a cost: an
on-topic question worded unlike anything in the notes is refused. Write notes
in the words customers use, and add a fake customer for any phrasing that
matters.

## 4. Argument validation

Every action has a JSON Schema. Arguments that do not fit it never reach a
rule or a handler; the model is told what is wrong and can try again.

## 5. Policy guard, on actions

Rules with a `tool` are checked before the action runs:

- `limits` bound an argument with `max`, `min` or a list of `allowed` values;
- `forbid: true` refuses the action outright.

A limit the guard cannot evaluate counts as broken. If a refund rule limits
`amount_inr` and the model leaves that argument out or passes text, the action
is refused, not waved through.

What happens next is the rule's `on_violation`. `block` refuses the action and
tells the model why, so it can explain to the customer. `handoff` ends the
rep's part in the conversation.

## 6. Reply guard

Two checks on the draft reply.

**Honesty.** A draft that says the rep is a person, or denies being an AI, is
replaced with the persona's `disclosure` line. This is not configurable and
applies to every pack. The rep may sound human; it may not claim to be one.

**`never_say`.** Each rule can list patterns a reply must never match. A draft
that matches is not sent, and the rule's `safe_reply` goes out instead. The
dental pack uses this to stop the rep naming a condition or a medicine; the
lettings pack uses it to stop the rep announcing a decision on an application.

A replaced draft is never added to the conversation history. The history
records what the customer saw, so the model does not build on a reply that was
not sent.

**What it does not do.** `never_say` matches wording. A model can break the
spirit of a rule in words no pattern anticipated. The patterns catch the
phrasings a rule's author thought of, cheaply and every time; they are not a
classifier.

## 7. Grounding check

With `ground_numbers` on, every number in a draft reply must appear somewhere
the rep could have read it: a rule or knowledge note looked up during this
conversation, a tool call or its result, the customer's own words, or one of
the pack's fixed lines such as the greeting. A number found in none of them is
an invented fact, and the pack's `unsure_reply` is sent instead.

Figures in the example chats do not count. Those conversations belong to other
customers, and a rep that repeats an order total from one of them is inventing.

It compares numbers as numbers, so "₹3,000" in a reply is grounded by "3000"
in a tool result.

**What it does not do.** It does not prove a reply is true. A wrong statement
with no number in it is not caught. A right number attached to the wrong thing
is not caught either: if the notes say a whitening costs ₹12,000 and the rep
says a filling does, the figure is "grounded".

## 8. Reply shaper

The last step makes the reply read like a chat message. It strips Markdown a
chat window would show literally, removes emoji when the persona does not use
them, cuts the persona's `banned_phrases`, and splits the reply into bubbles of
`max_sentences` each. At most three bubbles are sent.

## What all of this adds up to

The checks remove specific, common failures: answering off-topic requests,
taking an action past a limit, claiming to be human, saying a forbidden thing
in a way someone anticipated, and stating a figure from nowhere. Each one
leaves a trace when it fires.

They are not a guarantee that every reply is correct. That is the reason for
the other half of the project: every conversation is recorded, and fake
customers, some of them hostile, run against the pack on every change. See
[scenarios.md](scenarios.md).

One more limit, stated plainly. The tests in this repository run against
recorded and stand-in models, including recordings where the model misbehaves
on purpose. That proves the checks stop what they are meant to stop. It does
not measure how often the real model needs stopping, which takes a run with
`hamilton-harness sim PACK --live` and an API key.
