import { defineConfig, devices } from '@playwright/test';
import { existsSync } from 'node:fs';
import path from 'node:path';

const backendDir = path.resolve(process.cwd(), '..', 'backend');
const backendPythonCandidates = [
  path.join(backendDir, '.venv', 'bin', 'python'),
  path.join(backendDir, '.venv', 'Scripts', 'python.exe'),
];
const backendPython =
  backendPythonCandidates.find((candidate) => existsSync(candidate)) ?? 'python';
const e2eDatabasePath = path.join(backendDir, 'data', 'studysync-e2e.sqlite3');

process.env.STUDYSYNC_E2E_DB_PATH = e2eDatabasePath;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: `${backendPython} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      cwd: backendDir,
      env: {
        ...process.env,
        OPENAI_DOC_QA_ENABLED: '0',
        RESEND_API_KEY: '',
        STUDYSYNC_DB_BACKEND: 'sqlite',
        STUDYSYNC_DB_PATH: e2eDatabasePath,
      },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      url: 'http://127.0.0.1:8000/api/health',
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      url: 'http://127.0.0.1:5173',
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
