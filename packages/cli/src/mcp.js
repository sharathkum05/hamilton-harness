// The MCP server Claude talks to. Every tool is a call to the Hamilton server's
// dashboard API, so Claude edits through the same validated editor as the
// dashboard: a change that would break the rep is refused, with the reason.

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { z } from 'zod'

const INSTRUCTIONS = `This server manages one company's AI rep on a Hamilton server: who the rep
is, what it knows, what it may promise, the orders and quotes it has taken, and when a human
takes over.

Start with get_overview. Knowledge files are the facts the rep answers from; anything not in them
is something the rep should not state, so add facts there rather than to the persona. After
changing rules, scope or knowledge, call run_fake_customers and report the result: it shows
whether the rep still refuses what it should. Edits are validated; if one is refused, the message
says which field was wrong.`

const SECTIONS = ['persona', 'scope', 'widget', 'handoff']
const STATUSES = ['new', 'confirmed', 'done', 'cancelled']

export function buildServer(api) {
  const server = new McpServer({ name: 'hamilton-harness', version: '0.1.0' }, { instructions: INSTRUCTIONS })

  /** Run a call and hand Claude either the result or a message it can act on. */
  const tool = (name, description, inputSchema, work) =>
    server.registerTool(name, { description, inputSchema }, async (input) => {
      let result
      try {
        result = await work(input)
      } catch (error) {
        result = { ok: false, error: error.message }
      }
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] }
    })

  tool(
    'get_overview',
    "Everything about the rep at a glance: persona, scope, look, handoff rules, policy rules, the actions it can take, the record types it can take down, the names of its knowledge files, and recent activity counts.",
    {},
    async () => {
      const [pack, stats] = await Promise.all([api.pack(), api.overview()])
      return {
        ...pack,
        knowledge: pack.knowledge.map((doc) => ({ name: doc.source, characters: doc.text.length })),
        examples: pack.examples.map((chat) => chat.title),
        activity: { records: stats.records, conversations: stats.conversations },
      }
    },
  )

  tool(
    'update_settings',
    'Change some fields in one section and keep the rest. Sections: persona (name, company, role, voice, banned_phrases, disclosure), scope (covers, off_topic_reply, refuse, strict, ground_numbers), widget (greeting, accent, theme, title, suggestions, corners, font), handoff (phrases, on_request, message). Call get_overview for current values.',
    { section: z.enum(SECTIONS), changes: z.record(z.any()) },
    async ({ section, changes }) => {
      const pack = await api.pack()
      await api.saveSection(section, { ...pack[section], ...changes })
      return { ok: true, [section]: (await api.pack())[section] }
    },
  )

  tool(
    'read_knowledge',
    'Read one knowledge file, such as shipping.md.',
    { name: z.string() },
    async ({ name }) => {
      const doc = (await api.pack()).knowledge.find((item) => item.source === name)
      return doc ? { ok: true, name, text: doc.text } : { ok: false, error: `no knowledge file ${name}` }
    },
  )

  tool(
    'write_knowledge',
    'Create or replace a knowledge file. Use Markdown with clear headings: each heading becomes a section the rep can look up on its own.',
    { name: z.string(), text: z.string() },
    async ({ name, text }) => ({ ok: true, ...(await api.saveKnowledge(name, text)) }),
  )

  tool(
    'delete_knowledge',
    'Delete a knowledge file. The rep stops stating anything only that file held.',
    { name: z.string() },
    async ({ name }) => ({ ok: true, ...(await api.deleteKnowledge(name)) }),
  )

  tool(
    'save_rules',
    'Replace the full list of policy rules. Read the current list from get_overview first, change what is needed, and send the whole list back.',
    { rules: z.array(z.record(z.any())) },
    async ({ rules }) => ({ ok: true, ...(await api.saveSection('policies', rules)) }),
  )

  tool(
    'run_fake_customers',
    "Run the pack's test customers against the current configuration and return the scorecard. Run this after any change to rules, scope or knowledge.",
    {},
    () => api.runTests(),
  )

  tool(
    'list_records',
    'Orders, quotation requests and other records the rep has taken down for the business, newest first. Pass a type such as "order" or "quote" to filter.',
    { type: z.string().optional() },
    ({ type }) => api.records(type),
  )

  tool(
    'set_record_status',
    'Mark a record new, confirmed, done or cancelled.',
    { record_id: z.string(), status: z.enum(STATUSES) },
    async ({ record_id, status }) => ({ ok: true, record: await api.setRecordStatus(record_id, status) }),
  )

  tool(
    'recent_conversations',
    'Recent real conversations, newest first, flagged where the guard stepped in, a message was off topic, or a human took over.',
    {},
    () => api.conversations(),
  )

  tool(
    'get_conversation',
    'Every recorded step of one conversation, to see why the rep answered as it did.',
    { conversation_id: z.string() },
    ({ conversation_id }) => api.conversation(conversation_id),
  )

  return server
}

export async function serve(api) {
  await buildServer(api).connect(new StdioServerTransport())
}
