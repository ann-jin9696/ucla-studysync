import { expect, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';

export type TestUser = {
  fullName: string;
  email: string;
  password: string;
};

export function uniqueId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function testUser(label: string): TestUser {
  const id = uniqueId(label);
  return {
    fullName: `E2E ${label}`,
    email: `${id}@g.ucla.edu`,
    password: 'Playwright123!',
  };
}

export async function signup(page: Page, user: TestUser) {
  await page.goto('/signup');
  await page.getByLabel('Full name').fill(user.fullName);
  await page.getByLabel('UCLA email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByText('Check your email')).toBeVisible();
}

export async function login(page: Page, user: TestUser) {
  await page.goto('/login');
  await page.getByLabel('UCLA email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', { name: 'Log in' }).click();
}

export function latestEmailVerificationToken(email: string) {
  const token = uniqueId('e2e-verification-token');
  return runBackendScript(
    `
import sqlite3
import sys
from app.auth import hash_token
from app.config import get_database_path
from app.security import normalize_email

connection = sqlite3.connect(get_database_path())
token_hash = connection.execute(
    """
    SELECT token_hash
    FROM email_verification_tokens
    JOIN users ON users.id = email_verification_tokens.user_id
    WHERE lower(users.email) = lower(?)
    ORDER BY email_verification_tokens.id DESC
    LIMIT 1
    """,
    (normalize_email(sys.argv[1]),),
).fetchone()[0]
connection.execute(
    "UPDATE email_verification_tokens SET token_hash = ? WHERE token_hash = ?",
    (hash_token(sys.argv[2]), token_hash),
)
connection.commit()
connection.close()
print(sys.argv[2])
`,
    [email, token],
  );
}

export function latestPasswordResetToken(email: string) {
  const token = uniqueId('e2e-password-reset-token');
  return runBackendScript(
    `
import sqlite3
import sys
from app.auth import hash_token
from app.config import get_database_path
from app.security import normalize_email

connection = sqlite3.connect(get_database_path())
token_hash = connection.execute(
    """
    SELECT token_hash
    FROM password_reset_tokens
    JOIN users ON users.id = password_reset_tokens.user_id
    WHERE lower(users.email) = lower(?)
    ORDER BY password_reset_tokens.id DESC
    LIMIT 1
    """,
    (normalize_email(sys.argv[1]),),
).fetchone()[0]
connection.execute(
    "UPDATE password_reset_tokens SET token_hash = ? WHERE token_hash = ?",
    (hash_token(sys.argv[2]), token_hash),
)
connection.commit()
connection.close()
print(sys.argv[2])
`,
    [email, token],
  );
}

function runBackendScript(script: string, args: string[] = []) {
  const backendDir = path.resolve(process.cwd(), '..', 'backend');
  const pythonCandidates = [
    path.join(backendDir, '.venv', 'bin', 'python'),
    path.join(backendDir, '.venv', 'Scripts', 'python.exe'),
  ];
  const pythonExecutable =
    pythonCandidates.find((candidate) => existsSync(candidate)) ?? 'python';

  return execFileSync(pythonExecutable, ['-c', script, ...args], {
    cwd: backendDir,
    env: {
      ...process.env,
      STUDYSYNC_DB_BACKEND: 'sqlite',
      STUDYSYNC_DB_PATH:
        process.env.STUDYSYNC_E2E_DB_PATH ??
        path.join(backendDir, 'data', 'studysync-e2e.sqlite3'),
    },
    stdio: 'pipe',
  })
    .toString()
    .trim();
}
