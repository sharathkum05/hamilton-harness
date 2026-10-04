#!/usr/bin/env node
// hamilton-harness: connect Claude to a Hamilton server.
//
//   hamilton-harness login --url https://chat.example.com    sign in with the server's admin token
//   hamilton-harness status                                   show which rep you are connected to
//   hamilton-harness mcp                                      run the MCP server (Claude starts this)
//   hamilton-harness logout                                   forget the saved sign-in

import { createInterface } from 'node:readline'
import { parseArgs } from 'node:util'

import { ApiError, client } from '../src/api.js'
import { clearCredentials, loadCredentials, saveCredentials } from '../src/config.js'

const HELP = `hamilton-harness: connect Claude to a Hamilton server

  hamilton-harness login --url <server address> [--token <admin token>]
  hamilton-harness status
  hamilton-harness mcp
  hamilton-harness logout

Sign in once, then add it to Claude:

  claude mcp add hamilton -- npx -y hamilton-harness mcp

The admin token is printed by the server when it starts with --admin. It can also
be given as HAMILTON_ADMIN_TOKEN, with the address as HAMILTON_URL.`

/** Ask for the token without echoing it to the terminal. */
function askHidden(question) {
  return new Promise((resolve) => {
    const prompt = createInterface({ input: process.stdin, output: process.stderr, terminal: true })
    prompt._writeToOutput = (text) => {
      if (text.includes(question)) process.stderr.write(text)
    }
    prompt.question(question, (answer) => {
      prompt.close()
      process.stderr.write('\n')
      resolve(answer.trim())
    })
  })
}

function signedIn() {
  const credentials = loadCredentials()
  if (!credentials) {
    throw new ApiError(0, 'not signed in. Run: hamilton-harness login --url <server address>')
  }
  return client(credentials)
}

async function login(args) {
  const { values } = parseArgs({ args, options: { url: { type: 'string' }, token: { type: 'string' } } })
  if (!values.url) throw new ApiError(0, 'login needs --url, for example --url http://localhost:8000')
  const url = values.url.replace(/\/$/, '')
  const token = values.token || process.env.HAMILTON_ADMIN_TOKEN || (await askHidden('Admin token: '))
  if (!token) throw new ApiError(0, 'no token given')

  // Prove the address and token work before saving them.
  const pack = await client({ url, token }).pack()
  saveCredentials(url, token)
  console.log(`Signed in to ${url} as the admin of ${pack.persona.name} at ${pack.persona.company}.`)
  console.log('Add it to Claude with: claude mcp add hamilton -- npx -y hamilton-harness mcp')
}

async function status() {
  const api = signedIn()
  const [pack, stats] = await Promise.all([api.pack(), api.overview()])
  console.log(`${pack.persona.name} at ${pack.persona.company} (${pack.persona.role})`)
  console.log(`  knowledge files   ${pack.knowledge.length}`)
  console.log(`  rules             ${pack.policies.length}`)
  console.log(`  test customers    ${pack.scenarios}`)
  console.log(`  conversations     ${stats.conversations.total}`)
  console.log(`  waiting for you   ${stats.records.waiting} order(s) or quote(s)`)
}

async function main() {
  const [command, ...args] = process.argv.slice(2)
  switch (command) {
    case 'login':
      return login(args)
    case 'status':
      return status()
    case 'logout':
      clearCredentials()
      return console.log('Signed out.')
    case 'mcp': {
      const { serve } = await import('../src/mcp.js')
      return serve(signedIn())
    }
    case undefined:
    case 'help':
    case '--help':
    case '-h':
      return console.log(HELP)
    default:
      throw new ApiError(0, `unknown command "${command}". Run: hamilton-harness help`)
  }
}

main().catch((error) => {
  // stderr, so nothing here corrupts the MCP stream on stdout.
  console.error(`hamilton-harness: ${error.message}`)
  process.exit(1)
})
