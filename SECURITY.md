# Security

## Reporting a problem

Please do not describe a vulnerability in a public issue.

Report it privately through GitHub: on this repository's **Security** tab,
choose **Report a vulnerability**. If that option is not shown, open an issue
that says only that you have a security report, with no details, and a
maintainer will arrange a private channel.

Include what you did, what happened, and what you expected. A failing test or
a fake customer that reproduces it is the most useful thing you can send.

This is a personal open-source project with one maintainer. You should get a
reply within a week.

## What counts

Things this project treats as security problems:

- A customer message that makes the rep take an action a rule forbids, or that
  gets a reply past the reply guard, in a way a pack author could not have
  prevented by writing the rule correctly.
- Reading or changing a pack, a conversation or a record through the web API
  without the dashboard token.
- The dashboard token or a customer's identity signature being exposed or
  forgeable.
- A pack setting that reaches the page unescaped, or a pack file path that
  escapes the pack folder.
- The embed script letting the host page read the conversation, or the reverse.

Things that are expected behaviour, described in
[docs/guardrails.md](docs/guardrails.md):

- A reply that is wrong but breaks no rule and states no ungrounded figure.
  The checks remove specific failures; they do not prove a reply is true.
- A `never_say` pattern not matching a phrasing its author did not anticipate.

Those are still worth an ordinary issue, ideally with a fake customer that
shows the failure.

## If you run this yourself

- **Keep the dashboard token secret.** It is the only thing protecting
  `/api/admin`. Set `HAMILTON_ADMIN_TOKEN`, or let the server create one in
  its state folder, and serve the dashboard over HTTPS.
- **Handlers are your code.** A pack's `handlers.py` runs with the server's
  permissions. Only load packs you trust, and treat every argument as coming
  from a customer: the schema and the policy guard run first, but a handler
  should still check what it is given.
- **Set `HAMILTON_IDENTITY_SECRET`** before you pass customer identities from
  your site to the chat, so they are signed. See
  [docs/integrate.md](docs/integrate.md).
- **Restrict who may embed the chat** with `--allow-origin`.
- **Conversations are stored in plain files** in the state folder. Put that
  folder somewhere that suits what your customers will type into the chat.
