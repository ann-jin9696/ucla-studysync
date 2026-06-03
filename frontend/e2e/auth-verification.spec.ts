import { expect, test } from '@playwright/test';
import {
  latestEmailVerificationToken,
  login,
  signup,
  testUser,
} from './helpers';

test('unverified users are held at email verification before profile setup', async ({ page }) => {
  const user = testUser('verify');

  await signup(page, user);
  await page.goto('/dashboard');
  await expect(page.getByText('Check your email')).toBeVisible();

  const token = latestEmailVerificationToken(user.email);
  await page.goto(`/verify-email?token=${token}`);
  await expect(page.getByText('Email verified')).toBeVisible();

  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(
    page.getByRole('heading', { name: 'Tell StudySync what you are taking.' }),
  ).toBeVisible();

  await login(page, user);
  await expect(
    page.getByRole('heading', { name: 'Tell StudySync what you are taking.' }),
  ).toBeVisible();
});
