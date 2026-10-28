// Chapter 4. An agent manages the rep over MCP. This test plays the part of
// Claude: it starts the hamilton-harness npm package as an MCP server over
// stdio, exactly as Claude Code or Claude Desktop would, and calls its tools.
// Every edit goes through the same validated editor as the dashboard.

import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'
import { expect, test } from '@playwright/test'

import { ADMIN, HAMILTON } from './env'
import { openSection, signIn } from './helpers'

const CLI = fileURLToPath(new URL('../../packages/cli/bin/hamilton-harness.js', import.meta.url))

let claude: Client

/** What a tool call returned, parsed from the JSON text the server sends back. */
async function call(name: string, args: Record<string, unknown> = {}) {
  const result = await claude.callTool({ name, arguments: args })
  const [first] = result.content as { type: string; text: string }[]
  return JSON.parse(first.text)
}

test.beforeAll(async () => {
  claude = new Client({ name: 'e2e-as-claude', version: '1.0.0' })
  await claude.connect(
    new StdioClientTransport({
      command: process.execPath,
      args: [CLI, 'mcp'],
      env: {
        ...(process.env as Record<string, string>),
        HAMILTON_URL: HAMILTON,
        HAMILTON_ADMIN_TOKEN: ADMIN.token,
        // A config folder of its own, so a real saved sign-in is never read or changed.
        HAMILTON_CONFIG_DIR: mkdtempSync(join(tmpdir(), 'hamilton-e2e-')),
      },
    }),
  )
})

test.afterAll(async () => {
  await claude?.close()
})

test('the MCP server offers tools for managing the rep', async () => {
  const { tools } = await claude.listTools()
  const names = tools.map((tool) => tool.name)
  for (const name of ['get_overview', 'update_settings', 'write_knowledge', 'save_rules', 'run_fake_customers']) {
    expect(names).toContain(name)
  }
  const overview = await call('get_overview')
  expect(overview.persona.name).toBe('Maya')
  expect(overview.persona.company).toBe('Loop Sneakers')
})

test('an edit made over MCP reaches the live chat', async ({ page }) => {
  const greeting = 'Hello! Maya here, set up by Claude over MCP.'
  const changed = await call('update_settings', { section: 'widget', changes: { greeting } })
  expect(changed.ok).toBe(true)

  await page.goto('/chat?nopacing&inline')
  await expect(page.getByText(greeting)).toBeVisible()
})

test('an edit that would break the rep is refused, with the reason', async () => {
  const refused = await call('update_settings', { section: 'widget', changes: { accent: 'pink' } })
  expect(refused.ok).toBe(false)
  expect(refused.error).toMatch(/hex colour/)
})

test('knowledge written over MCP shows up in the dashboard', async ({ page }) => {
  const written = await call('write_knowledge', {
    name: 'gift-cards.md',
    text: '## Gift cards\nGift cards come in ₹1,000 and ₹2,500 and never expire.',
  })
  expect(written.ok).toBe(true)

  await signIn(page)
  await openSection(page, 'Knowledge')
  await expect(page.getByText('gift-cards.md').first()).toBeVisible()
})

test('the agent can run the fake customers after its change', async () => {
  const report = await call('run_fake_customers')
  expect(report.summary.passed).toBe(report.summary.scenarios)
})
