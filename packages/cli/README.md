# hamilton-harness

Connect Claude to a Hamilton server. Sign in once, then ask Claude to manage your
AI rep: add knowledge, tighten its scope, change a rule, work through the
orders and quotes it has taken, or rerun the tests.

## Use

Start your Hamilton server with the dashboard switched on. It prints an admin
token.

```bash
hamilton-harness serve packs/your-company --admin
```

Install it, or use `npx` as below and skip the install:

```bash
npm install -g hamilton-harness
```

Sign in from the machine where Claude runs. The token is asked for without
being shown, checked against the server, and saved in a file only you can read.

```bash
npx hamilton-harness login --url https://chat.example.com
```

Add it to Claude Code:

```bash
claude mcp add hamilton -- npx -y hamilton-harness mcp
```

Or to Claude Desktop, in its MCP settings:

```json
{
  "mcpServers": {
    "hamilton": { "command": "npx", "args": ["-y", "hamilton-harness", "mcp"] }
  }
}
```

Then ask in plain words: "add our new returns policy to the knowledge", "stop
it discussing competitors", "show me today's quotation requests and mark the
first one confirmed", "rerun the fake customers".

## Commands

| Command | What it does |
|---|---|
| `hamilton-harness login --url <address>` | Check the address and token, then save them |
| `hamilton-harness status` | Show which rep you are connected to and what is waiting |
| `hamilton-harness mcp` | Run the MCP server. Claude starts this itself |
| `hamilton-harness logout` | Forget the saved sign-in |

In CI or a container, set `HAMILTON_URL` and `HAMILTON_ADMIN_TOKEN` instead of
signing in.

## What Claude can do

`get_overview`, `update_settings`, `read_knowledge`, `write_knowledge`,
`delete_knowledge`, `save_rules`, `run_fake_customers`, `list_records`,
`set_record_status`, `recent_conversations`, `get_conversation`.

Every edit goes through the server's own validated editor. A change that would
leave the rep unable to load is rolled back and refused, and Claude is told
which field was wrong.
