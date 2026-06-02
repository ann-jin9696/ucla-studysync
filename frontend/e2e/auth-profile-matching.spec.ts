import { expect, test } from '@playwright/test';
import {
  completeProfile,
  createGroup,
  logout,
  signupVerifyAndLogin,
  testUser,
  uniqueId,
} from './helpers';

test('signup, login, profile setup, and group matching flow', async ({ page }) => {
  const owner = testUser('owner');
  const applicant = testUser('applicant');
  const groupName = uniqueId('E2E Review Crew');

  await signupVerifyAndLogin(page, owner);
  await completeProfile(page);
  await createGroup(page, groupName);
  await logout(page);

  await signupVerifyAndLogin(page, applicant);
  await completeProfile(page);
  await page.getByRole('button', { name: /Group matching/ }).click();

  const applicantGroupCard = page.locator('.directory-group-card', { hasText: groupName });
  await expect(applicantGroupCard).toBeVisible();
  await applicantGroupCard.getByRole('button', { name: 'Apply' }).click();
  await expect(applicantGroupCard.getByText('Application pending.')).toBeVisible();
  await expect(applicantGroupCard.getByRole('button', { name: 'Withdraw' })).toBeVisible();
  await logout(page);

  await page.goto('/login');
  await page.getByLabel('UCLA email').fill(owner.email);
  await page.getByLabel('Password').fill(owner.password);
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page.getByRole('heading', { name: /Hi, / })).toBeVisible();

  await page.getByRole('button', { name: /Group matching/ }).click();
  const ownerGroupCard = page.locator('.directory-group-card', { hasText: groupName });
  await expect(ownerGroupCard.getByText(applicant.fullName)).toBeVisible();
  await ownerGroupCard.getByRole('button', { name: 'Allow', exact: true }).click();
  await expect(page.getByText('Applicant approved.')).toBeVisible();
  await expect(ownerGroupCard.getByText('2 members')).toBeVisible();
});
