# Keeping the data in Supabase

By default a running rep keeps its data in the state folder (`.hamilton/`).
That works for one server on one machine. To keep it in a database instead, so
it survives redeploys, can be backed up and can be shared by several servers,
point Hamilton at Postgres. Supabase is the quickest way to get one.

## What goes in the database

| Kept in the database | Kept as files |
|---|---|
| Orders, quotes and other records the rep takes down | The pack: persona, knowledge, rules, widget |
| What the rep remembers about signed-in customers | The admin token and demo login |
| Every recorded turn, which the Conversations and Overview screens read | |

The pack stays as plain files on purpose, so it can live in Git and every
change to it can be reviewed. Chats that are open right now are held in the
server's memory; what they say is written to the database turn by turn.

## 1. Get the connection string

1. Create a project at [supabase.com](https://supabase.com), and note the
   database password you set.
2. Open the project and click **Connect** at the top.
3. Copy the **Session pooler** connection string. It works from any network.
   The direct connection needs IPv6, which many home and office networks do
   not have.
4. Put your database password in place of `[YOUR-PASSWORD]`.

It looks like this:

```
postgresql://postgres.abcdefghijklmnop:YOUR-PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

## 2. Install the database packages

```bash
pip install -e ".[db]"
```

## 3. Start Hamilton with it

Keep the connection string out of Git. A `.env` file, which this repository
already ignores, or your shell is the place for it:

```bash
export HAMILTON_DATABASE_URL='postgresql://postgres.abcdefghijklmnop:YOUR-PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'
```

```bash
hamilton-harness studio my-assistant
```

The first line it prints says where the data is going, with the password
hidden:

```
Keeping orders, memory and conversations in postgresql+psycopg://postgres.abcdefghijklmnop:***@aws-0-ap-south-1.pooler.supabase.com:5432/postgres.
```

On first start Hamilton creates a `hamilton` schema with three tables:
`records`, `customers` and `trace_events`. `serve` works the same way. The
`demo` command always uses files, because it starts clean on every run.

## 4. See the data

In Supabase, open **Table Editor** and choose the `hamilton` schema. Each row
has a `rep` column with the name of the rep's folder, so several reps can share
one project without mixing.

## Security

- **The tables are not on Supabase's public API.** Supabase serves the
  `public` schema to anyone holding the project's anon key. Hamilton's tables
  are in `hamilton`, which it does not serve unless you add it under
  **Settings → API → Exposed schemas**. Do not add it.
- **Customer ids are stored as hashes.** A customer's email or phone number,
  if that is their id, is never written to the database.
- **The connection string is a password.** Anyone with it can read every
  conversation. Keep it in your hosting provider's secret settings, never in
  the repository.
- **For production, give Hamilton its own database user.** The `postgres` user
  can do anything. In the SQL editor:

  ```sql
  create role hamilton_app login password 'a long random password';
  create schema if not exists hamilton authorization hamilton_app;
  ```

  Then use `hamilton_app` and its password in the connection string. It can
  read and write its own schema and nothing else.

## Any other Postgres

Nothing here is specific to Supabase. Any Postgres connection string works,
whether that is Neon, RDS, Cloud SQL or a server of your own. For a quick local
try, SQLite works too:

```bash
export HAMILTON_DATABASE_URL='sqlite:///hamilton.db'
```
