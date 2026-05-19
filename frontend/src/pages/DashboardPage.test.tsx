import { render, screen } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { Profile } from '../api';
import { DashboardPage } from './DashboardPage';

const baseProfile: Profile = {
  courses: ['CS35L'],
  study_goals: [],
  pace_preference: null,
  study_style_preference: null,
  group_size_preference: null,
  preferred_study_time_tags: [],
  has_basic_profile: true,
  is_complete: false,
  created_at: '',
  updated_at: '',
};

let profileState: { profile: Profile } = {
  profile: baseProfile,
};

vi.mock('../components/AuthProvider', () => ({
  useAuth: () => ({
    user: { id: 1, full_name: 'Sunny Bruin', email: 'sunny@g.ucla.edu', created_at: '' },
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
  it('shows a reminder for basic incomplete profiles', () => {
    profileState = {
      profile: {
        ...baseProfile,
        is_complete: false,
        study_goals: [],
        pace_preference: null,
        study_style_preference: null,
      },
    };

    renderDashboard();

    expect(screen.getByText('Finish your profile for better group matches')).toBeInTheDocument();
    expect(
      screen.getByText('Still missing: study goals, pace preference, study style preference.'),
    ).toBeInTheDocument();
  });

  it('hides the reminder for complete profiles', () => {
    profileState = {
      profile: {
        ...baseProfile,
        study_goals: ['exam_prep'],
        pace_preference: 'moderate',
        study_style_preference: 'problem_solving',
        is_complete: true,
      },
    };

    renderDashboard();

    expect(
      screen.queryByText('Finish your profile for better group matches'),
    ).not.toBeInTheDocument();
  });
});
