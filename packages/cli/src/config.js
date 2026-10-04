// Where the CLI keeps the server address and admin token between runs.

import { chmodSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

export function configDir() {
  return process.env.REPKIT_CONFIG_DIR || join(homedir(), '.config', 'repkit')
}

const file = () => join(configDir(), 'credentials.json')

/** The saved sign-in, or null. Environment variables win, for CI and containers. */
export function loadCredentials() {
  if (process.env.REPKIT_URL && process.env.REPKIT_ADMIN_TOKEN) {
    return { url: process.env.REPKIT_URL.replace(/\/$/, ''), token: process.env.REPKIT_ADMIN_TOKEN }
  }
  if (!existsSync(file())) return null
  try {
    const saved = JSON.parse(readFileSync(file(), 'utf8'))
    return saved.url && saved.token ? saved : null
  } catch {
    return null
  }
}

export function saveCredentials(url, token) {
  mkdirSync(configDir(), { recursive: true })
  writeFileSync(file(), JSON.stringify({ url, token }, null, 2))
  // The token is a password: only the owner may read it.
  chmodSync(file(), 0o600)
}

export function clearCredentials() {
  rmSync(file(), { force: true })
}
