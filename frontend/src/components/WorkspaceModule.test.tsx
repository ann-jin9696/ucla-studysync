import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import type { ComponentProps } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { groupApi } from '../api';
import { WorkspaceModule } from './WorkspaceModule';

const apiMocks = vi.hoisted(() => ({
  askDocuments: vi.fn(),
  createComment: vi.fn(),
  deleteDocument: vi.fn(),
  documentFileUrl: vi.fn(() => ''),
  getDetail: vi.fn(),
  listComments: vi.fn(),
  listDocuments: vi.fn(),
  listMyGroups: vi.fn(),
  uploadDocument: vi.fn(),
}));

vi.mock('../api', () => ({
  groupApi: apiMocks,
}));

const alphaGroup = {
  id: 1,
  name: 'Alpha Group',
  course_id: 1,
  course_code: 'CS35L',
  course_quarter: 'Spring 2026',
  lecture_number: 1,
  created_by_user_id: 1,
  member_count: 3,
  created_at: '2026-05-23 20:00:00',
  updated_at: '2026-05-23 20:00:00',
};

const betaGroup = {
  ...alphaGroup,
  id: 2,
  name: 'Beta Group',
};

const documentsByGroup = {
  1: [
    {
      id: 10,
      group_id: 1,
      uploader_id: 1,
      uploader_name: 'Ann',
      title: 'Alpha Notes',
      file_name: 'alpha-notes.pdf',
      file_path: 'uploads/group-1/alpha-notes.pdf',
      file_size_bytes: 123,
      document_type: 'notes',
      index_status: 'ready' as const,
      index_error: null,
      ai_summary: 'This one-sentence summary covers Alpha setup notes.',
      can_delete: true,
      uploaded_at: '2026-05-23 20:00:00',
    },
    {
      id: 11,
      group_id: 1,
      uploader_id: 1,
      uploader_name: 'Ann',
      title: 'Plain Text Notes',
      file_name: 'plain-text-notes.txt',
      file_path: 'uploads/group-1/plain-text-notes.txt',
      file_size_bytes: 123,
      document_type: 'notes',
      index_status: 'ready' as const,
      index_error: null,
      ai_summary: null,
      can_delete: true,
      uploaded_at: '2026-05-23 20:01:00',
    },
    {
      id: 12,
      group_id: 1,
      uploader_id: 1,
      uploader_name: 'Ann',
      title: 'Markdown Study Guide',
      file_name: 'markdown-study-guide.md',
      file_path: 'uploads/group-1/markdown-study-guide.md',
      file_size_bytes: 123,
      document_type: 'review',
      index_status: 'ready' as const,
      index_error: null,
      ai_summary: null,
      can_delete: true,
      uploaded_at: '2026-05-23 20:02:00',
    },
  ],
  2: [
    {
      id: 20,
      group_id: 2,
      uploader_id: 2,
      uploader_name: 'Audrey',
      title: 'Beta Guide',
      file_name: 'beta-guide.pdf',
      file_path: 'uploads/group-2/beta-guide.pdf',
      file_size_bytes: 123,
      document_type: 'review',
      index_status: 'ready' as const,
      index_error: null,
      ai_summary: 'This one-sentence summary covers the Beta guide.',
      can_delete: true,
      uploaded_at: '2026-05-23 20:05:00',
    },
  ],
};

const commentsByDocument = {
  10: [
    {
      id: 100,
      document_id: 10,
      author_id: 1,
      author_name: 'Ann',
      content: 'Alpha follow-up note.',
      created_at: '2026-05-23 20:10:00',
    },
  ],
  20: [
    {
      id: 300,
      document_id: 20,
      author_id: 2,
      author_name: 'Audrey',
      content: 'This is the exact comment to revisit.',
      created_at: '2026-05-23 20:15:00',
    },
  ],
};

const betaGroupDetail = {
  ...betaGroup,
  owner_name: 'Ann',
  top_study_goals: [
    { value: 'project_work', count: 2 },
    { value: 'exam_prep', count: 1 },
  ],
  average_pace_preference: 'moderate',
  average_pace_score: 2,
  group_size_bucket: 'small',
  members: [
    {
      user_id: 1,
      full_name: 'Ann',
      is_owner: true,
      study_goals: ['project_work'],
      pace_preference: 'moderate',
      group_size_preference: 4,
      joined_at: '2026-05-23 20:00:00',
    },
    {
      user_id: 2,
      full_name: 'Audrey',
      is_owner: false,
      study_goals: ['project_work', 'exam_prep'],
      pace_preference: 'moderate',
      group_size_preference: 4,
      joined_at: '2026-05-23 20:05:00',
    },
  ],
};

const scrollIntoViewMock = vi.fn();

function renderWorkspace(props: Partial<ComponentProps<typeof WorkspaceModule>> = {}) {
  return render(
    <ConfigProvider>
      <WorkspaceModule mode="workspace" {...props} />
    </ConfigProvider>,
  );
}

describe('WorkspaceModule', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window.HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoViewMock,
    });
    vi.spyOn(window, 'getComputedStyle').mockImplementation(
      () =>
        ({
          getPropertyValue: () => '',
        }) as unknown as CSSStyleDeclaration,
    );
    vi.mocked(groupApi.listMyGroups).mockResolvedValue([alphaGroup, betaGroup]);
    vi.mocked(groupApi.listDocuments).mockImplementation(async (groupId: number) => ({
      group_id: groupId,
      documents: documentsByGroup[groupId as 1 | 2],
    }));
    vi.mocked(groupApi.listComments).mockImplementation(
      async (_groupId: number, documentId: number) =>
        commentsByDocument[documentId as 10 | 20] ?? [],
    );
    vi.mocked(groupApi.getDetail).mockResolvedValue(betaGroupDetail);
    vi.mocked(groupApi.askDocuments).mockResolvedValue({
      answer: 'Alpha notes say to compare setup steps.',
      sources: [
        {
          document_id: 10,
          file_name: 'alpha-notes.pdf',
          snippet: 'Compare your setup and bring one question.',
        },
      ],
    });
    vi.mocked(groupApi.documentFileUrl).mockImplementation(
      (groupId: number, documentId: number) =>
        `/api/groups/${groupId}/documents/${documentId}/file`,
    );
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        return {
          ok: true,
          text: async () =>
            url.includes('/12/')
              ? '# Markdown Preview\n\n- First item\n- Second item'
              : 'Plain text preview body.',
          blob: async () => new Blob(['preview'], { type: 'application/pdf' }),
        } as Response;
      }),
    );
  });

  it('lets a user switch between multiple group workspaces', async () => {
    const user = userEvent.setup();

    renderWorkspace();

    expect(await screen.findByText('Alpha Notes')).toBeInTheDocument();
    expect(
      screen.getByText('This one-sentence summary covers Alpha setup notes.'),
    ).toBeInTheDocument();
    expect(screen.getAllByText('AI').length).toBeGreaterThan(0);
    expect(groupApi.listDocuments).toHaveBeenCalledWith(1, '');

    await user.click(
      screen.getByRole('button', { name: 'Beta Group CS35L Spring 2026 Lec 1' }),
    );

    expect(await screen.findByText('Beta Guide')).toBeInTheDocument();
    expect(screen.queryByText('Alpha Notes')).not.toBeInTheDocument();

    await waitFor(() => {
      expect(groupApi.listDocuments).toHaveBeenLastCalledWith(2, '');
    });
  });

  it('scrolls and highlights a document opened from recent activity', async () => {
    renderWorkspace({
      initialGroupId: 2,
      initialDocumentId: 20,
      focusActivityId: 'document-20',
      focusRequestId: 1,
    });

    const documentRow = await screen.findByRole('button', { name: /Beta Guide/ });

    expect(documentRow).toHaveClass('focused-activity');
    await waitFor(() => {
      expect(scrollIntoViewMock).toHaveBeenCalled();
    });
  });

  it('shows the AI summary on document rows and the preview modal', async () => {
    const user = userEvent.setup();

    renderWorkspace();

    expect(await screen.findByText('Alpha Notes')).toBeInTheDocument();
    expect(
      screen.getByText('This one-sentence summary covers Alpha setup notes.'),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Alpha Notes/ }));

    expect(
      screen.getAllByText('This one-sentence summary covers Alpha setup notes.'),
    ).toHaveLength(2);
    expect(screen.getAllByText('AI').length).toBeGreaterThan(1);
  });

  it('scrolls and highlights a comment opened from recent activity', async () => {
    renderWorkspace({
      mode: 'discussion',
      initialGroupId: 2,
      initialDocumentId: 20,
      focusActivityId: 'comment-300',
      focusRequestId: 1,
    });

    const commentText = await screen.findByText('This is the exact comment to revisit.');
    const commentItem = commentText.closest('.comment-item');

    expect(commentItem).toHaveClass('focused-activity');
    await waitFor(() => {
      expect(scrollIntoViewMock).toHaveBeenCalled();
    });
  });

  it('opens details for the selected group workspace', async () => {
    const user = userEvent.setup();

    renderWorkspace({ initialGroupId: 2 });

    await screen.findByText('Beta Guide');
    await user.click(screen.getByRole('button', { name: 'Group info' }));

    expect(await screen.findByText('Group properties')).toBeInTheDocument();
    expect(screen.getAllByText('Ann').length).toBeGreaterThan(0);
    expect(screen.getByText('Audrey')).toBeInTheDocument();
    expect(groupApi.getDetail).toHaveBeenCalledWith(2);
  });

  it('asks questions against the selected group documents', async () => {
    const user = userEvent.setup();

    renderWorkspace();

    await screen.findByText('Alpha Notes');
    await user.type(
      screen.getByPlaceholderText("Ask a question about this group's shared files"),
      'What should we compare?',
    );
    await user.click(screen.getByRole('button', { name: 'Ask' }));

    expect(await screen.findByText('Alpha notes say to compare setup steps.')).toBeInTheDocument();
    expect(screen.getByText('alpha-notes.pdf')).toBeInTheDocument();
    expect(screen.getByText('Compare your setup and bring one question.')).toBeInTheDocument();
    expect(groupApi.askDocuments).toHaveBeenCalledWith(1, 'What should we compare?');
  });

  it('previews text and markdown documents in the workspace modal', async () => {
    const user = userEvent.setup();

    const { unmount } = renderWorkspace();

    const textTitle = await screen.findByText('Plain Text Notes');
    await user.click(textTitle.closest('button') as HTMLButtonElement);

    expect(await screen.findByText('Plain text preview body.')).toBeInTheDocument();

    unmount();
    renderWorkspace();

    const markdownTitle = await screen.findByText('Markdown Study Guide');
    await user.click(markdownTitle.closest('button') as HTMLButtonElement);

    expect(await screen.findByRole('heading', { name: 'Markdown Preview' })).toBeInTheDocument();
    expect(screen.getByText('First item')).toBeInTheDocument();
    expect(screen.getByText('Second item')).toBeInTheDocument();
  });

  it('does not upload files outside the supported preview types', async () => {
    const user = userEvent.setup();
    const { container } = renderWorkspace();

    await screen.findByText('Alpha Notes');
    await user.type(screen.getByLabelText('Title'), 'Unsupported Upload');
    await user.upload(
      container.querySelector('input[type="file"]') as HTMLInputElement,
      new File(['gif'], 'animation.gif', { type: 'image/gif' }),
    );
    await user.click(screen.getByRole('button', { name: 'Upload document' }));

    expect(groupApi.uploadDocument).not.toHaveBeenCalled();
  });
});
