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

export async function signupVerifyAndLogin(page: Page, user: TestUser) {
  await page.goto('/signup');
  await page.getByLabel('Full name').fill(user.fullName);
  await page.getByLabel('UCLA email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByText('Check your email')).toBeVisible();

  markEmailVerified(user.email);

  await page.goto('/login');
  await login(page, user);
}

export async function login(page: Page, user: TestUser) {
  await page.getByLabel('UCLA email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', { name: 'Log in' }).click();
}

export async function logout(page: Page) {
  await page.getByRole('button', { name: 'Logout' }).click();
  await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();
}

export async function completeProfile(page: Page, courseCode = 'CS35L') {
  await expect(page.getByRole('heading', { name: 'Tell StudySync what you are taking.' })).toBeVisible();

  await page.getByRole('combobox', { name: /Course code/ }).fill(courseCode);
  await page.getByRole('combobox', { name: 'Study goals' }).click();
  await page.getByTitle('Exam prep').click();
  await page.keyboard.press('Escape');

  await page.getByRole('combobox', { name: 'Pace' }).click();
  await page.getByTitle('Moderate').click();

  await page.getByRole('spinbutton', { name: 'Group size' }).fill('4');
  await page.getByRole('button', { name: 'Save profile' }).click();
  await expect(page.getByRole('heading', { name: /Hi, / })).toBeVisible();
}

export async function createGroup(page: Page, groupName: string) {
  await page.getByRole('button', { name: /Group matching/ }).click();
  await expect(page.getByRole('heading', { name: 'Course groups' })).toBeVisible();
  await page.getByPlaceholder('Group name').fill(groupName);
  await page.getByRole('button', { name: 'Create group' }).click();
  await expect(page.locator('.directory-group-card', { hasText: groupName })).toBeVisible();
}

function markEmailVerified(email: string) {
  const backendDir = path.resolve(process.cwd(), '..', 'backend');
  const venvPython = path.join(backendDir, '.venv', 'Scripts', 'python.exe');
  const pythonExecutable = existsSync(venvPython) ? venvPython : 'python';
  const script = `
import sqlite3
import sys
from app.config import get_database_path
from app.security import normalize_email

connection = sqlite3.connect(get_database_path())
connection.execute(
    "UPDATE users SET email_verified = 1 WHERE lower(email) = lower(?)",
    (normalize_email(sys.argv[1]),),
)
connection.commit()
connection.close()
`;

  execFileSync(pythonExecutable, ['-c', script, email], {
    cwd: backendDir,
    stdio: 'pipe',
  });
}
