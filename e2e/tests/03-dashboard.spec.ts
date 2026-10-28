// Chapter 3. The dashboard: the business changes its rep without code, sees
// each stage of the harness, sets up tools, and tests every change.

import { expect, test } from '@playwright/test'

import { ADMIN } from './env'
import { openSection, signIn } from './helpers'

test('the dashboard needs the admin email and password', async ({ page }) => {
  await page.goto('/admin')
  await page.getByLabel('Email').fill(ADMIN.email)
  await page.getByLabel('Password').fill('not-the-password')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toHaveText('That email and password do not match.')

  await page.getByLabel('Password').fill(ADMIN.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Maya at Loop Sneakers')
})

test('the flow shows each stage of the harness, and where a message stopped', async ({ page }) => {
  await signIn(page)
  await openSection(page, 'Flow')
  const stages = page.getByRole('list', { name: 'Stages of a turn' }).getByRole('listitem')
  await expect(stages).toHaveCount(9)

  await page.getByRole('button', { name: 'What is 348 * 12?' }).click()
  const scope = stages.filter({ hasText: 'Scope gate' })
  await expect(scope.getByText('Stopped it')).toBeVisible()
  await expect(stages.filter({ hasText: 'Model' }).getByText('Not reached')).toBeVisible()

  await page.getByLabel('Test message').fill("refund LS-5120, I just don't like them")
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const tools = stages.filter({ hasText: /^Tools/ })
  await expect(tools.getByText('Stopped it')).toBeVisible()
  await expect(tools).toContainText('issue_refund')
})

test('a tool can be tried with sample inputs', async ({ page }) => {
  await signIn(page)
  await openSection(page, 'Tools')
  await page.getByPlaceholder('Order number such as LS-4471.').fill('LS-4471')
  await page.getByRole('button', { name: 'Run' }).first().click()
  await expect(page.getByText('It worked')).toBeVisible()
  await expect(page.getByText('"status": "shipped"')).toBeVisible()
})

test('a change in the dashboard reaches the chat at once', async ({ page }) => {
  await signIn(page)
  await openSection(page, 'Brand')
  const greeting = 'Hi from the dashboard! What can I do for you?'
  await page.locator('#greeting').fill(greeting)
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByText('Brand saved')).toBeVisible()
  // The live preview beside the screen starts over with the new greeting.
  await expect(page.frameLocator('iframe[title="Chat preview"]').getByText(greeting)).toBeVisible()

  await page.goto('/chat?nopacing&inline')
  await expect(page.getByText(greeting)).toBeVisible()
})

test('every change can be tested against the fake customers', async ({ page }) => {
  await signIn(page)
  await openSection(page, 'Test')
  await page.getByRole('button', { name: 'Run fake customers' }).click()
  await expect(page.getByText(/^(\d+) of \1 passed$/)).toBeVisible({ timeout: 30_000 })
})
