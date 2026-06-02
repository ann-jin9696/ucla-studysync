import { expect, test } from '@playwright/test';
import {
  completeProfile,
  createGroup,
  signupVerifyAndLogin,
  testUser,
  uniqueId,
} from './helpers';

test('workspace upload, search, preview, and comment flow', async ({ page }) => {
  const user = testUser('workspace');
  const groupName = uniqueId('E2E Workspace Crew');
  const documentTitle = uniqueId('E2E Week 5 Notes');
  const fileName = `${documentTitle}.txt`;
  const fileBody = 'Playwright preview content for StudySync shared workspace.';
  const comment = uniqueId('This is an e2e workspace comment');

  await signupVerifyAndLogin(page, user);
  await completeProfile(page);
  await createGroup(page, groupName);

  await page.getByRole('button', { name: /Shared workspaces/ }).click();
  await expect(
    page.locator('.workspace-shell').getByRole('heading', { name: 'Shared workspaces' }),
  ).toBeVisible();
  await page.getByLabel('Group workspaces').getByText(groupName).click();

  await page.getByLabel('Title').fill(documentTitle);
  await page.locator('input[type="file"]').setInputFiles({
    name: fileName,
    mimeType: 'text/plain',
    buffer: Buffer.from(fileBody),
  });
  await page.getByRole('button', { name: 'Upload document' }).click();
  await expect(page.getByText('Document uploaded.')).toBeVisible();

  await page.getByPlaceholder('Search title, file name, or type').fill('Week 5');
  await page.getByRole('button', { name: 'Search' }).click();
  const uploadedDocument = page.locator('.document-row', { hasText: documentTitle });
  await expect(uploadedDocument).toBeVisible();
  await uploadedDocument.click();
  const previewDialog = page.getByRole('dialog', { name: documentTitle });
  await expect(previewDialog).toBeVisible();
  await expect(page.getByText(fileBody)).toBeVisible();
  await previewDialog.locator('.ant-modal-close').click();

  await page.getByRole('button', { name: /Group discussion/ }).click();
  await expect(
    page.locator('.workspace-shell').getByRole('heading', { name: 'Group discussion' }),
  ).toBeVisible();
  await page.getByPlaceholder('Search discussion material').fill(documentTitle);
  await page.getByRole('button', { name: 'Search' }).click();
  await page.locator('.document-row', { hasText: documentTitle }).click();
  await page.getByPlaceholder('Leave a note for your group').fill(comment);
  await page.getByRole('button', { name: 'Post comment' }).click();
  await expect(page.getByText('Comment added.')).toBeVisible();
  await expect(page.locator('.comment-item', { hasText: comment })).toBeVisible();
});
