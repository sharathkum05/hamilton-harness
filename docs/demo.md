# Showing Hamilton

A ten-minute walkthrough, in the order it is best told. Every step is also a
Playwright test in [`e2e/tests`](../e2e/tests), run in a real browser on every
push, so the demo is known to work before it is shown.

```bash
npm --prefix web ci && npm --prefix web run build
npm --prefix e2e ci
npm --prefix e2e test
```

`npm --prefix e2e run record` runs the same steps slowed down and films each
one, to `e2e/test-results`. `npm --prefix e2e run hosted` checks the live site.

| Chapter | Show | Test |
|---|---|---|
| 1. The harness | `/demo`: ask about order LS-4471. The inspector shows the rule and notes the rep was given and the `lookup_order` call | [01-harness](../e2e/tests/01-harness.spec.ts) |
| 2. The guardrails | Refund over the limit: blocked. "Match 40% off": reply replaced. "348 × 12": refused, model never called. "A real person": handed over. A prompt injection: blocked | [02-guardrails](../e2e/tests/02-guardrails.spec.ts) |
| 3. The dashboard | Sign in. Flow: send "What is 348 * 12?" and watch the scope gate stop it. Tools: try `lookup_order`. Brand: change the greeting and watch the preview. Test: run the fake customers | [03-dashboard](../e2e/tests/03-dashboard.spec.ts) |
| 4. An agent over MCP | Claude, through the `hamilton-harness` npm package, reads the rep, changes the greeting, is refused a bad colour with the reason, adds a knowledge file and runs the fake customers | [04-mcp](../e2e/tests/04-mcp.spec.ts) |
| 5. Any website | A shop's own site on another address shows the chat from one script tag. A PHP page signs in its customer with an HMAC | [05-embed](../e2e/tests/05-embed.spec.ts) |
| 6. Deployed | The same app live on Vercel, with a read-only dashboard | [06-hosted](../e2e/tests/06-hosted.spec.ts) |

## What to say at each step

1. **"One model becomes a company's rep."** Everything that changes between
   companies is a folder of YAML and Markdown; the harness code is the same.
2. **"A prompt asks. Code enforces."** Each guardrail runs in code around the
   model, so it holds even when the model is talked into something. The demo's
   stand-in model misbehaves on purpose, so every check has something to stop.
3. **"A business changes it without code, and tests every change."** The Flow
   screen is the harness itself: the order of the stages is fixed, so no
   setting can route a reply around the guard.
4. **"An agent can run it too."** The MCP server goes through the same
   validated editor as the dashboard, so Claude cannot break the rep either.
5. **"It goes on any site."** One script tag, in its own frame; a site with
   signed-in customers signs their id on its server.
6. **"And it is deployed."** CI runs the unit tests, the fake customers and
   this walkthrough before Vercel deploys.
