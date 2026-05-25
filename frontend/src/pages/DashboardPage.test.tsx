import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { groupApi, type Profile, type ProfileInput } from '../api';
import { DashboardPage } from './DashboardPage';

const baseCourse = {
  user_course_id: 1,
  course_id: 1,
  course_code: 'CS35L',
  course_quarter: 'Spring 2026',
  lecture_number: 1,
  study_goals: [],
  pace_preference: null,
  group_size_preference: null,
};

const baseProfile: Profile = {
  courses: [baseCourse],
  has_basic_profile: true,
  is_complete: false,
  created_at: '',
  updated_at: '',
};

const saveProfile = vi.fn(async (input: ProfileInput) => ({
  ...baseProfile,
  ...input,
  courses: input.courses.map((course, index) => ({
    ...course,
    user_course_id: index + 1,
    course_id: index + 1,
  })),
}));

let profileState: { profile: Profile; error: string | null; saveProfile: typeof saveProfile } = {
  profile: baseProfile,
  error: null,
  saveProfile,
};

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    groupApi: {
      listMyGroups: vi.fn(async () => []),
      listActivity: vi.fn(async () => []),
      create: vi.fn(),
      apply: vi.fn(),
      leave: vi.fn(),
      listJoinRequests: vi.fn(async () => []),
      approveJoinRequest: vi.fn(),
      rejectJoinRequest: vi.fn(),
      withdrawJoinRequest: vi.fn(),
      listDocuments: vi.fn(async () => ({ group_id: 1, documents: [] })),
      uploadDocument: vi.fn(),
      listComments: vi.fn(async () => []),
      createComment: vi.fn(),
      documentFileUrl: vi.fn(() => ''),
    },
    matchingApi: {
      listGroups: vi.fn(async () => []),
    },
  };
});

vi.mock('../components/AuthProvider', () => ({
  useAuth: () => ({
    user: {
      id: 1,
      full_name: 'Sunny Bruin',
      email: 'sunny@g.ucla.edu',
      email_verified: true,
      notify_group_application_news: true,
      created_at: '',
    },
    logout: vi.fn(),
  }),
}));

vi.mock('../components/ProfileProvider', () => ({
  useProfile: () => profileState,
}));

function renderDashboard() {
  return render(
    <ConfigProvider>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </ConfigProvider>,
  );
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(groupApi.listActivity).mockResolvedValue([]);
  });

  it('shows a reminder for basic incomplete profiles', async () => {
    profileState = {
      profile: {
        ...baseProfile,
        is_complete: false,
        courses: [{ ...baseCourse, study_goals: [], pace_preference: null }],
      },
      error: null,
      saveProfile,
    };

    renderDashboard();
    await screen.findByText('No recent activity');

    expect(screen.getByText('Finish your profile for better group matches')).toBeInTheDocument();
    expect(
      screen.getByText('Still missing: study goals, pace preference.'),
    ).toBeInTheDocument();
  });

  it('hides the reminder for complete profiles', async () => {
    profileState = {
      profile: {
        ...baseProfile,
        courses: [
          {
            ...baseCourse,
            study_goals: ['exam_prep'],
            pace_preference: 'moderate',
          },
        ],
        is_complete: true,
      },
      error: null,
      saveProfile,
    };

    renderDashboard();
    await screen.findByText('No recent activity');

    expect(
      screen.queryByText('Finish your profile for better group matches'),
    ).not.toBeInTheDocument();
  });

  it('opens profile setup inside the dashboard module area', async () => {
    profileState = {
      profile: {
        ...baseProfile,
        is_complete: false,
        courses: [{ ...baseCourse, study_goals: [], pace_preference: null }],
      },
      error: null,
      saveProfile,
    };

    renderDashboard();
    await screen.findByText('No recent activity');

    await userEvent.click(screen.getByText('Profile setup'));

    expect(screen.getByText('Study profile')).toBeInTheDocument();
    expect(screen.getByLabelText('Course code')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save profile' })).toBeInTheDocument();
  });

  it('uses the dashboard module instead of a top-nav edit profile action', async () => {
    profileState = {
      profile: {
        ...baseProfile,
        is_complete: false,
        courses: [{ ...baseCourse, study_goals: [], pace_preference: null }],
      },
      error: null,
      saveProfile,
    };

    renderDashboard();
    await screen.findByText('No recent activity');

    expect(screen.queryByRole('button', { name: 'Edit profile' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Finish profile' }));

    expect(screen.getByText('Study profile')).toBeInTheDocument();
    expect(screen.getByLabelText('Course code')).toBeInTheDocument();
  });

  it('shows recent activity from the group API above the module cards', async () => {
    vi.mocked(groupApi.listActivity).mockResolvedValueOnce([
      {
        id: 'document-1',
        activity_type: 'document_uploaded',
        group_id: 4,
        group_name: 'CS35L Study Hub',
        course_code: 'CS35L',
        document_id: 1,
        document_title: 'Midterm Review Notes',
        actor_id: 2,
        actor_name: 'Ann',
        occurred_at: new Date().toISOString(),
      },
    ]);

    renderDashboard();

    expect(await screen.findByText('Midterm Review Notes')).toBeInTheDocument();
    expect(groupApi.listActivity).toHaveBeenCalled();

    const activityFeed = document.querySelector('.activity-feed');
    const moduleMenu = document.querySelector('.module-menu');

    expect(activityFeed).not.toBeNull();
    expect(moduleMenu).not.toBeNull();
    expect(
      activityFeed!.compareDocumentPosition(moduleMenu!) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('opens shared workspace from an uploaded-document activity', async () => {
    vi.mocked(groupApi.listActivity).mockResolvedValueOnce([
      {
        id: 'document-1',
        activity_type: 'document_uploaded',
        group_id: 4,
        group_name: 'CS35L Study Hub',
        course_code: 'CS35L',
        document_id: 1,
        document_title: 'Midterm Review Notes',
        actor_id: 2,
        actor_name: 'Ann',
        occurred_at: new Date().toISOString(),
      },
    ]);

    renderDashboard();

    await userEvent.click(
      await screen.findByRole('button', { name: 'View Midterm Review Notes' }),
    );

    expect(document.querySelector('.workspace-shell')?.textContent).toContain(
      'Shared workspaces',
    );
  });

  it('lets group matching use the selected module card style', async () => {
    profileState = {
      profile: baseProfile,
      error: null,
      saveProfile,
    };

    renderDashboard();
    await screen.findByText('No recent activity');

    const matchingCard = screen.getByRole('button', {
      name: 'Group matching Browse course groups, filter by fit, and apply to join.',
    });

    await userEvent.click(matchingCard);

    expect(matchingCard).toHaveAttribute('aria-pressed', 'true');
    expect(matchingCard).toHaveClass('active-module-card');
    expect(screen.getByText('Groups for CS35L')).toBeInTheDocument();
  });
});
