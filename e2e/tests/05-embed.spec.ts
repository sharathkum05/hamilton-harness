// Chapter 5. The chat on a company's existing website: one script tag, on a
// site at a different address that knows nothing about Hamilton. The PHP page
// also signs in its customer, so the rep knows who it is talking to.

import { existsSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { HAMILTON, PHP, SITE } from './env'
import { chat, openSection, say, signIn } from './helpers'

const hasPhp = Boolean(process.env.PATH?.split(':').some((dir) => existsSync(`${dir}/php`)))

test('one script tag puts the chat on an existing website', async ({ page }) => {
  await page.goto(SITE)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Shoes that loop back to you.')
  // The only Hamilton markup on the page is the script tag.
  await expect(page.locator(`script[src="${HAMILTON}/widget.js"]`)).toHaveCount(1)

  await page.locator('#hamilton-widget').getByRole('button', { name: /^Chat with/ }).click()
  const frame = page.locator('#hamilton-widget iframe')
  // The chat runs in a frame served by Hamilton, so the shop's styles cannot break it.
  await expect(frame).toHaveAttribute('src', new RegExp(`^${HAMILTON}/chat`))
  await say(page, "hey where's my order LS-4471")
  await expect(chat(page).getByText(/Thursday 8 October/)).toBeVisible()
})

test('the example site shows the one line to copy', async ({ page }) => {
  await page.goto('/example')
  await expect(page.locator('#snippet')).toHaveText(`<script src="${HAMILTON}/widget.js" defer></script>`)
})

test('the dashboard gives the line for any kind of site, PHP included', async ({ page }) => {
  await signIn(page)
  await openSection(page, 'Install')
  for (const kind of ['Any website', 'PHP', 'WordPress', 'React / Next.js']) {
    await expect(page.getByRole('tab', { name: kind })).toBeVisible()
  }
  await page.getByRole('tab', { name: 'PHP' }).click()
  await expect(page.getByText(/hash_hmac\('sha256'/)).toBeVisible()
})

test('a PHP site signs in its customer and the chat works there', async ({ page }) => {
  test.skip(!hasPhp, 'PHP is not installed here: brew install php')
  await page.goto(PHP)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Hello, Priya')
  const tag = page.locator(`script[src="${HAMILTON}/widget.js"]`)
  await expect(tag).toHaveAttribute('data-hamilton-customer', 'priya@example.com')
  await expect(tag).toHaveAttribute('data-hamilton-signature', /^[0-9a-f]{64}$/)

  await page.locator('#hamilton-widget').getByRole('button', { name: /^Chat with/ }).click()
  await say(page, "hey where's my order LS-4471")
  await expect(chat(page).getByText(/Thursday 8 October/)).toBeVisible()
})
