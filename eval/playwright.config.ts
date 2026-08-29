import path from 'node:path'

import { defineConfig } from '@playwright/test'
import dotenv from 'dotenv'

dotenv.config({ path: path.resolve(__dirname, '.env'), quiet: true })

export default defineConfig({
  testDir: './tests',
  // Sequential on purpose: cases share one seeded session + DB pool, and
  // generation calls hit a real chat model, so serial runs keep timing/token
  // readings clean and avoid tripping provider rate limits.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.API_BASE_URL ?? 'http://localhost:8000',
  },
})
