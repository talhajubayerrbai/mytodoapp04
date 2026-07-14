import { defineConfig, devices } from '@playwright/test';

const APP_URL = process.env.APP_URL || 'http://localhost:8000';

export default defineConfig({
  testDir: './tests',
  /* Maximum time one test can run */
  timeout: 60_000,
  /* Maximum time the whole test suite can run */
  globalTimeout: 20 * 60_000,
  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,
  /* No retries */
  retries: 0,
  /* Opt out of parallel tests on CI to avoid DB race conditions */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter: list in terminal + HTML for upload */
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'playwright-report/results.json' }],
  ],

  use: {
    /* Base URL so tests can use relative paths */
    baseURL: APP_URL,
    /* Capture screenshot only on failure */
    screenshot: 'only-on-failure',
    /* Record video for every test — useful for debugging flaky tests */
    video: 'on',
    /* Collect trace on first retry */
    trace: 'on-first-retry',
    /* Navigation timeout */
    navigationTimeout: 30_000,
    /* Action timeout */
    actionTimeout: 15_000,
  },

  /* Test against Chromium only */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /* Output folders */
  outputDir: 'test-results',
});
