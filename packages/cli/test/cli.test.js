import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { mkdtempSync, statSync } from 'node:fs'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { after, before, test } from 'node:test'
import { promisify } from 'node:util'

import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js'

import { client } from '../src/api.js'
import { buildServer } from '../src/mcp.js'

const run = promisify(execFile)
const BIN = new URL('../bin/hamilton-harness.js', import.meta.url).pathname
const TOKEN = 'test-token'

// A stand-in for a Hamilton server's dashboard API, with just enough behaviour to test against.
const state = {
  pack: {
    persona: { name: 'Maya', company: 'Loop Sneakers', role: 'customer support' },
    scope: { strict: false, covers: 'orders' },
    widget: { accent: 'auto' },
    handoff: { phrases: [] },
    policies: [{ id: 'refund-limit' }],
    knowledge: [{ source: 'shipping.md', text: '# Shipping\nThree days.' }],
    examples: [{ title: 'late-order' }],
    scenarios: 16,
  },
  records: [{ id: 'QUO-0001', type: 'quote', status: 'new', data: { quantity: 40 } }],
}

let server
let url

before(async () => {
  server = createServer(async (request, response) => {
    const send = (status, body) => {
      response.writeHead(status, { 'content-type': 'application/json' })
      response.end(JSON.stringify(body))
    }
    if (request.headers.authorization !== `Bearer ${TOKEN}`) return send(401, { detail: 'no' })
    let raw = ''
    for await (const chunk of request) raw += chunk
    const body = raw ? JSON.parse(raw) : undefined
    const path = request.url.replace('/api/admin', '')

    if (path === '/pack') return send(200, state.pack)
    if (path === '/overview') {
      return send(200, { records: { waiting: 1, total: 1 }, conversations: { total: 7 } })
    }
    if (path === '/pack/widget' && request.method === 'PUT') {
      if (body.accent === 'tomato') return send(422, { detail: 'accent: must be a hex colour' })
      state.pack.widget = body
      return send(200, { saved: 'widget' })
    }
    if (path === '/pack/scope' && request.method === 'PUT') {
      state.pack.scope = body
      return send(200, { saved: 'scope' })
    }
    if (path.startsWith('/knowledge/') && request.method === 'PUT') {
      state.pack.knowledge.push({ source: decodeURIComponent(path.slice(11)), text: body.text })
      return send(200, { saved: path.slice(11) })
    }
    if (path.startsWith('/records') && request.method === 'GET') return send(200, { records: state.records })
    if (path === '/records/QUO-0001' && request.method === 'PATCH') {
      state.records[0].status = body.status
      return send(200, state.records[0])
    }
    if (path === '/sim') return send(200, { summary: { passed: 16, scenarios: 16 }, results: [] })
    return send(404, { detail: 'not found' })
  })
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
  url = `http://127.0.0.1:${server.address().port}`
})

after(() => server.close())

/** Connect a real MCP client to the server, in memory, and call a tool. */
async function callTool(name, args = {}) {
  const [clientSide, serverSide] = InMemoryTransport.createLinkedPair()
  const mcp = buildServer(client({ url, token: TOKEN }))
  await mcp.connect(serverSide)
  const caller = new Client({ name: 'test', version: '0' })
  await caller.connect(clientSide)
  const result = await caller.callTool({ name, arguments: args })
  await caller.close()
  return JSON.parse(result.content[0].text)
}

test('the tools Claude sees are listed with descriptions', async () => {
  const [clientSide, serverSide] = InMemoryTransport.createLinkedPair()
  await buildServer(client({ url, token: TOKEN })).connect(serverSide)
  const caller = new Client({ name: 'test', version: '0' })
  await caller.connect(clientSide)
  const { tools } = await caller.listTools()
  const names = tools.map((tool) => tool.name)
  for (const expected of ['get_overview', 'update_settings', 'write_knowledge', 'list_records', 'run_fake_customers']) {
    assert.ok(names.includes(expected), expected)
  }
  assert.ok(tools.every((tool) => tool.description.length > 20))
  await caller.close()
})

test('the overview names knowledge files without their text', async () => {
  const overview = await callTool('get_overview')
  assert.equal(overview.persona.name, 'Maya')
  assert.deepEqual(overview.knowledge[0], { name: 'shipping.md', characters: 22 })
  assert.equal(overview.activity.records.waiting, 1)
})

test('settings are merged, not replaced', async () => {
  const result = await callTool('update_settings', { section: 'scope', changes: { strict: true } })
  assert.equal(result.ok, true)
  assert.deepEqual(result.scope, { strict: true, covers: 'orders' })
})

test('a refused edit comes back as a message, not a crash', async () => {
  const result = await callTool('update_settings', { section: 'widget', changes: { accent: 'tomato' } })
  assert.equal(result.ok, false)
  assert.match(result.error, /hex colour/)
  assert.equal(state.pack.widget.accent, 'auto')
})

test('knowledge can be written and read back', async () => {
  await callTool('write_knowledge', { name: 'gift-cards.md', text: '# Gift cards\nNever expire.' })
  const read = await callTool('read_knowledge', { name: 'gift-cards.md' })
  assert.equal(read.text, '# Gift cards\nNever expire.')
  assert.equal((await callTool('read_knowledge', { name: 'nope.md' })).ok, false)
})

test('records can be listed and marked', async () => {
  assert.equal((await callTool('list_records')).records[0].id, 'QUO-0001')
  const marked = await callTool('set_record_status', { record_id: 'QUO-0001', status: 'confirmed' })
  assert.equal(marked.record.status, 'confirmed')
})

test('a wrong token is explained', async () => {
  const [clientSide, serverSide] = InMemoryTransport.createLinkedPair()
  await buildServer(client({ url, token: 'wrong' })).connect(serverSide)
  const caller = new Client({ name: 'test', version: '0' })
  await caller.connect(clientSide)
  const result = await caller.callTool({ name: 'get_overview', arguments: {} })
  assert.match(JSON.parse(result.content[0].text).error, /admin token was not accepted/)
  await caller.close()
})

test('login checks the token, saves it privately, and status reads it', async () => {
  const env = { ...process.env, HAMILTON_CONFIG_DIR: mkdtempSync(join(tmpdir(), 'hamilton-')) }
  delete env.HAMILTON_URL
  delete env.HAMILTON_ADMIN_TOKEN

  await assert.rejects(run('node', [BIN, 'status'], { env }), /not signed in/)
  await assert.rejects(run('node', [BIN, 'login', '--url', url, '--token', 'wrong'], { env }), /not accepted/)

  const login = await run('node', [BIN, 'login', '--url', `${url}/`, '--token', TOKEN], { env })
  assert.match(login.stdout, /Maya at Loop Sneakers/)
  assert.ok(!login.stdout.includes(TOKEN))
  const saved = statSync(join(env.HAMILTON_CONFIG_DIR, 'credentials.json'))
  assert.equal(saved.mode & 0o077, 0)

  const status = await run('node', [BIN, 'status'], { env })
  assert.match(status.stdout, /test customers\s+16/)

  await run('node', [BIN, 'logout'], { env })
  await assert.rejects(run('node', [BIN, 'status'], { env }), /not signed in/)
})
