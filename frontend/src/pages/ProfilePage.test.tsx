import { render, screen } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { Profile, ProfileInput } from '../api';
import { ProfilePage } from './ProfilePage';

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

let profileState: {
  profile: Profile;
  error: string | null;
  saveProfile: (input: ProfileInput) => Promise<Profile>;
} = {
  profile: baseProfile,
  error: null,
  saveProfile: vi.fn(async () => baseProfile),
};

vi.mock('../components/AuthProvider', () => ({
  useAuth: () => ({
    logout: vi.fn(),
  }),
}));

vi.mock('../components/ProfileProvider', () => ({
  useProfile: () => profileState,
}));

function renderProfilePage() {
  return render(
    <ConfigProvider>
      <MemoryRouter>
        <ProfilePage mode="edit" />
      </MemoryRouter>
    </ConfigProvider>,
  );
}

describe('ProfilePage', () => {
  it('shows missing required sections for incomplete profiles', () => {
    profileState = {
      ...profileState,
      profile: {
        ...baseProfile,
        study_goals: [],
        pace_preference: null,
        study_style_preference: null,
        is_complete: false,
      },
    };

    renderProfilePage();

    expect(screen.getByText('Finish your profile')).toBeInTheDocument();
    expect(screen.getByText(/study goals/)).toBeInTheDocument();
    expect(screen.getByText(/pace preference/)).toBeInTheDocument();
    expect(screen.getByText(/study style preference/)).toBeInTheDocument();
  });

  it('removes the reminder for complete profiles', () => {
    profileState = {
      ...profileState,
      profile: {
        ...baseProfile,
        study_goals: ['exam_prep'],
        pace_preference: 'moderate',
        study_style_preference: 'problem_solving',
        is_complete: true,
      },
    };

    renderProfilePage();

    expect(screen.queryByText('Finish your profile')).not.toBeInTheDocument();
  });
});
