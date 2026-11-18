// Chapter 3. The dashboard: the business changes its rep without code, sees
// each stage of the harness, sets up tools, and tests every change.

import { expect, test } from '@playwright/test'

import { ADMIN } from './env'
import { openSection, signIn } from './helpers'

test('the dashboard needs the admin user ID and passcode', async ({ page }) => {
  await page.goto('/admin')
  await page.getByLabel('User ID').fill(ADMIN.user)
  const passcode = page.getByLabel('Passcode', { exact: true })
  await passcode.fill('not-the-passcode')
  // The passcode can be shown, to check what was typed.
  await page.getByRole('button', { name: 'Show passcode' }).click()
  await expect(passcode).toHaveAttribute('type', 'text')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toHaveText('That user ID and passcode do not match.')

  await passcode.fill(ADMIN.password)
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

test('the account screen shows who is signed in, and signs out', async ({ page }) => {
  await signIn(page)
  await page.getByText(ADMIN.user, { exact: true }).first().click()
  await page.getByRole('menuitem', { name: 'Account' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Account' })).toBeVisible()
  await expect(page.getByText(/^Until (today|tomorrow) at/)).toBeVisible()
  // This server's passcode comes from the environment, so it is changed there, not here.
  await expect(page.getByText(/HAMILTON_ADMIN_PASSWORD; change it there/)).toBeVisible()

  await page.getByRole('main').getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('heading', { name: 'Sign in to the dashboard' })).toBeVisible()
})
