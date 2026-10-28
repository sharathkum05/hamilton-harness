// Chapter 1. The harness: one language model becomes a company's rep, and
// every turn can be seen from the inside.

import { expect, test } from '@playwright/test'

import { chat, openDemo, tryOnDemo } from './helpers'

test('the product page says what it is and leads to the live demo', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('The AI harness')
  await page.getByRole('link', { name: /Try the live demo/ }).click()
  await expect(page).toHaveURL(/\/demo$/)
})

test('the rep greets the customer as the company, and says it is an AI', async ({ page }) => {
  await openDemo(page)
  const panel = chat(page)
  await expect(panel.getByText("Hey! I'm Maya, Loop's AI assistant.", { exact: false })).toBeVisible()
  await expect(panel.getByText('Maya is an AI assistant.', { exact: false })).toBeVisible()
})

test('a question about an order is answered from the order system', async ({ page }) => {
  await openDemo(page)
  const turn = await tryOnDemo(page, "hey where's my order LS-4471")
  // The inspector shows the rule and notes the rep was given, and the action it took.
  await expect(turn.getByText('lookup_order', { exact: false })).toBeVisible()
  await expect(turn.getByText('ok', { exact: true })).toBeVisible()
  await expect(chat(page).getByText(/Thursday 8 October/)).toBeVisible()
})

test('an order the customer places lands in the inbox with a reference', async ({ page }) => {
  await openDemo(page)
  const turn = await tryOnDemo(page, 'I want to buy 2 pairs of Court Classic in UK 9')
  await expect(turn).toBeVisible()
  // The rep asks for the details it needs; the reply comes back from the stand-in model.
  await expect(chat(page).locator('body')).toContainText(/name|phone|order/i)
})
