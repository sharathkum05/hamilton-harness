// Small steps the chapters share: the chat in its frame, the demo inspector,
// and signing in to the dashboard.

import { expect } from '@playwright/test'
import type { FrameLocator, Locator, Page } from '@playwright/test'

import { ADMIN } from './env'

/** The chat panel, inside the frame the embed script adds to any page. */
export function chat(page: Page): FrameLocator {
  // Playwright's CSS reaches into the widget's open shadow root.
  return page.frameLocator('#hamilton-widget iframe')
}

/** Type a message into the chat and wait for the rep's reply to finish arriving. */
export async function say(page: Page, text: string): Promise<Locator> {
  const panel = chat(page)
  const box = panel.getByRole('textbox', { name: 'Message' })
  await expect(box).toBeEnabled()
  await box.fill(text)
  await box.press('Enter')
  // The rep is "typing" until every bubble is in; the box is enabled again after.
  await expect(panel.getByText(text, { exact: true }).last()).toBeVisible()
  await expect(box).toBeEnabled({ timeout: 20_000 })
  return panel.locator('body')
}

/** The newest card in the demo page's "Under the hood" inspector. */
export function latestTurn(page: Page): Locator {
  return page.locator('section[aria-labelledby="hood"] [data-slot="card"]').first()
}

/** Open the demo page with the chat open and the inspector ready. */
export async function openDemo(page: Page) {
  await page.goto('/demo')
  await expect(page.getByText('inspector on')).toBeVisible()
  await expect(chat(page).getByRole('textbox', { name: 'Message' })).toBeVisible()
}

/** Click one of the demo's "Things to try" and wait for its turn in the inspector. */
export async function tryOnDemo(page: Page, text: string): Promise<Locator> {
  await page.getByRole('button', { name: new RegExp(`^${escape(text)}`) }).click()
  const turn = latestTurn(page)
  await expect(turn.getByText(text, { exact: true })).toBeVisible({ timeout: 20_000 })
  await expect(turn.getByText(/model calls? ·/)).toBeVisible()
  return turn
}

/** Sign in to the dashboard with the admin email and password. */
export async function signIn(page: Page, section = 'overview') {
  await page.goto(`/admin#${section}`)
  const email = page.getByLabel('Email')
  if (await email.isVisible().catch(() => false)) {
    await email.fill(ADMIN.email)
    await page.getByLabel('Password').fill(ADMIN.password)
    await page.getByRole('button', { name: 'Sign in' }).click()
  }
  await expect(page.getByRole('button', { name: 'Sign out' }).first()).toBeAttached()
}

/** Open one dashboard screen from the sidebar. */
export async function openSection(page: Page, name: string) {
  await page.locator('[data-sidebar="menu-button"]').filter({ hasText: new RegExp(`^${name}$`) }).click()
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
}

function escape(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
