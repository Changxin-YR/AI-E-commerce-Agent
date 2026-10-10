import { expect, type Locator } from '@playwright/test'

// Exercise the retained precision path; ordinary native selection has separate
// timezone/DST and desktop/mobile continuity scenarios.
export async function fillExactTime(input: Locator, value: string): Promise<void> {
  const details = input.locator('..')
  // The ISO field belongs directly to its advanced details element.
  if ((await details.getAttribute('open')) === null) await details.locator('summary').click()
  await expect(input).toBeEnabled()
  await input.fill(value)
}
