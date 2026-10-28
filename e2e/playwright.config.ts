// End-to-end tests that walk through the demo the way it is shown in an
// interview, in order: the harness, the guardrails, the dashboard, Claude
// managing the rep over MCP, the chat on an existing website, and the hosted
// deployment.
//
//   npm test           run every chapter against a local server
//   npm run record     the same, slowed down and filmed, for a walkthrough video
//   npm run hosted     check the live deployment on Vercel

import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

import { ADMIN, HAMILTON, HAMILTON_PORT, PHP, PHP_PORT, SITE, SITE_PORT } from './tests/env'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
// The repository's own virtualenv when there is one, else whatever is installed.
const BIN = existsSync(`${ROOT}.venv/bin/hamilton-harness`)
  ? `${ROOT}.venv/bin/hamilton-harness`
  : 'hamilton-harness'
const hasPhp = Boolean(process.env.PATH?.split(':').some((dir) => existsSync(`${dir}/php`)))
// A real Chrome where one is installed saves downloading Playwright's own.
const chrome = !process.env.CI && existsSync('/Applications/Google Chrome.app')
const browser = { ...devices['Desktop Chrome'], ...(chrome ? { channel: 'chrome' } : {}) }

export default defineConfig({
  testDir: './tests',
  // The chapters tell one story and some change the rep, so they run in order.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: HAMILTON, trace: 'retain-on-failure' },
  projects: [
    { name: 'local', testIgnore: /hosted/, use: browser },
    {
      name: 'demo-video',
      testIgnore: /hosted/,
      use: {
        ...browser,
        video: { mode: 'on', size: { width: 1280, height: 800 } },
        viewport: { width: 1280, height: 800 },
        launchOptions: { slowMo: 350 },
      },
    },
    {
      name: 'hosted',
      testMatch: /hosted/,
      use: { ...browser, baseURL: 'https://hamilton-harness.vercel.app' },
    },
  ],
  webServer: [
    {
      // One rep, Loop Sneakers, on a throwaway copy: nothing here touches packs/.
      // The two example sites are listed, so they may show the chat.
      command:
        `"${BIN}" demo packs/loop-sneakers --port ${HAMILTON_PORT} --state .hamilton/e2e` +
        ` --allow-origin ${SITE} --allow-origin ${PHP}`,
      cwd: ROOT,
      url: `${HAMILTON}/healthz`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        HAMILTON_ADMIN_TOKEN: ADMIN.token,
        HAMILTON_ADMIN_EMAIL: ADMIN.email,
        HAMILTON_ADMIN_PASSWORD: ADMIN.password,
        HAMILTON_IDENTITY_SECRET: ADMIN.identitySecret,
      },
    },
    {
      // A company's existing website, on another address, that knows nothing about Hamilton.
      command: `python3 -m http.server ${SITE_PORT} --bind 127.0.0.1 --directory fixtures/site`,
      url: `http://127.0.0.1:${SITE_PORT}/`,
      reuseExistingServer: !process.env.CI,
    },
    ...(hasPhp
      ? [
          {
            command: `php -S 127.0.0.1:${PHP_PORT} -t fixtures/php-site`,
            url: `http://127.0.0.1:${PHP_PORT}/`,
            reuseExistingServer: !process.env.CI,
            env: {
              HAMILTON_URL: HAMILTON,
              HAMILTON_IDENTITY_SECRET: ADMIN.identitySecret,
            },
          },
        ]
      : []),
  ],
})
