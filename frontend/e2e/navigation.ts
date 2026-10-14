import type { Page } from '@playwright/test'

export async function openNavigation(page: Page) {
  const menu = page.getByRole('button', { name: '展开导航菜单', exact: true })
  if (await menu.isVisible()) await menu.click()
  return page.getByRole('navigation', { name: '主导航' })
}
