import process from 'node:process'
import path from 'node:path'
import { defineConfig, devices } from '@playwright/test'

const python = path.resolve(
  '../backend/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:5174', headless: true, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `"${python}" ../backend/scripts/serve_e2e.py`,
      url: 'http://127.0.0.1:8001/api/health/ready',
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: 'npm run preview -- --host 127.0.0.1 --port 5174 --strictPort',
      url: 'http://127.0.0.1:5174',
      // Exercise the production build; Playwright owns the preview server lifetime.
      env: { SOLOOPS_API_TARGET: 'http://127.0.0.1:8001', CI: 'true' },
      reuseExistingServer: false,
    },
  ],
})
