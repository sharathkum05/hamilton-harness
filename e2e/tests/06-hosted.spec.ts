// Chapter 6. The deployment: the same app, live on Vercel. Run with
// `npm run hosted`. It only reads and chats; the hosted dashboard is read-only.

import { expect, test } from '@playwright/test'

import { chat, openDemo, tryOnDemo } from './helpers'

test('the live site is up and leads to the demo', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('The AI harness')
})

test('the live demo answers and shows each turn from the inside', async ({ page }) => {
  await openDemo(page)
  const turn = await tryOnDemo(page, 'what is 348 * 12')
  await expect(turn.getByText(/Off topic \(math\)/)).toBeVisible()
  await expect(chat(page).locator('body')).toContainText(/Loop/)
})

test('the live dashboard opens read-only, with no sign-in', async ({ page }) => {
  await page.goto('/admin')
  await expect(page.getByText('Read-only demo')).toBeVisible()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Maya at Loop Sneakers')
})

test('the live example site carries the chat', async ({ page }) => {
  await page.goto('/example')
  await expect(page.locator('#hamilton-widget')).toBeAttached()
})
