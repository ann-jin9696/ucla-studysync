import { expect, test } from '@playwright/test';
import {
  latestEmailVerificationToken,
  latestPasswordResetToken,
  login,
  signup,
  testUser,
} from './helpers';

test('password reset replaces the old password and signs in with the new password', async ({ page }) => {
  const user = testUser('reset');
  const newPassword = 'Playwright456!';

  await signup(page, user);
  await page.goto(`/verify-email?token=${latestEmailVerificationToken(user.email)}`);
  await expect(page.getByText('Email verified')).toBeVisible();

  await page.goto('/forgot-password');
  await page.getByLabel('UCLA email').fill(user.email);
  await page.getByRole('button', { name: 'Send recovery email' }).click();
  await expect(page.getByText('Recovery email sent')).toBeVisible();

  await page.goto(`/reset-password?token=${latestPasswordResetToken(user.email)}`);
  await page.getByLabel('New password').fill(newPassword);
  await page.getByRole('button', { name: 'Reset password' }).click();
  await expect(page).toHaveURL(/\/profile\/setup$/);

  await page.goto('/login');
  await page.getByLabel('UCLA email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page.getByText('Email or password is incorrect.')).toBeVisible();

  await login(page, { ...user, password: newPassword });
  await expect(
    page.getByRole('heading', { name: 'Tell StudySync what you are taking.' }),
  ).toBeVisible();
});
