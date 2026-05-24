import { render, screen } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { Profile, ProfileInput } from '../api';
import { ProfilePage } from './ProfilePage';

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
        <ProfilePage />
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
        courses: [{ ...baseCourse, study_goals: [], pace_preference: null }],
        is_complete: false,
      },
    };

    renderProfilePage();

    expect(screen.getByText('Finish your profile')).toBeInTheDocument();
    expect(screen.getByText(/study goals/)).toBeInTheDocument();
    expect(screen.getByText(/pace preference/)).toBeInTheDocument();
  });

  it('removes the reminder for complete profiles', () => {
    profileState = {
      ...profileState,
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
    };

    renderProfilePage();

    expect(screen.queryByText('Finish your profile')).not.toBeInTheDocument();
  });
});
