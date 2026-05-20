import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { Profile, User } from '../api';
import { ProfileGate } from './ProfileGate';
import { ProtectedRoute } from './ProtectedRoute';

type AuthState = {
  user: User | null;
  loading: boolean;
};

type ProfileState = {
  profile: Profile | null;
  loading: boolean;
};

const baseUser: User = {
  id: 1,
  full_name: 'Test Bruin',
  email: 'test@g.ucla.edu',
  created_at: '',
};

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

let authState: AuthState = {
  user: baseUser,
  loading: false,
};

let profileState: ProfileState = {
  profile: baseProfile,
  loading: false,
};

vi.mock('./AuthProvider', () => ({
  useAuth: () => authState,
}));

vi.mock('./ProfileProvider', () => ({
  useProfile: () => profileState,
}));

function renderRoutes(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <ProfileGate requireBasicProfile>
                <p>Dashboard screen</p>
              </ProfileGate>
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile/setup"
          element={
            <ProtectedRoute>
              <ProfileGate redirectCompleteSetup>
                <p>Profile setup screen</p>
              </ProfileGate>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<p>Login screen</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProfileGate', () => {
  it('protects profile setup from logged-out users', () => {
    authState = { user: null, loading: false };
    profileState = { profile: baseProfile, loading: false };

    renderRoutes('/profile/setup');

    expect(screen.getByText('Login screen')).toBeInTheDocument();
  });

  it('redirects dashboard users without courses to setup', () => {
    authState = {
      user: baseUser,
      loading: false,
    };
    profileState = {
      profile: {
        ...baseProfile,
        courses: [],
        has_basic_profile: false,
        is_complete: false,
      },
      loading: false,
    };

    renderRoutes('/dashboard');

    expect(screen.getByText('Profile setup screen')).toBeInTheDocument();
  });

  it('does not redirect while profile state is loading', () => {
    authState = {
      user: baseUser,
      loading: false,
    };
    profileState = { profile: baseProfile, loading: true };
    const { container } = renderRoutes('/dashboard');

    expect(container.querySelector('.ant-spin')).toBeInTheDocument();
    expect(screen.queryByText('Profile setup screen')).not.toBeInTheDocument();
  });

  it('lets basic incomplete users keep editing setup', () => {
    authState = {
      user: baseUser,
      loading: false,
    };
    profileState = {
      profile: {
        ...baseProfile,
        courses: ['CS35L'],
        has_basic_profile: true,
        is_complete: false,
      },
      loading: false,
    };

    renderRoutes('/profile/setup');

    expect(screen.getByText('Profile setup screen')).toBeInTheDocument();
  });

  it('redirects complete users away from setup to dashboard', () => {
    authState = {
      user: baseUser,
      loading: false,
    };
    profileState = {
      profile: {
        ...baseProfile,
        study_goals: ['exam_prep'],
        pace_preference: 'moderate',
        study_style_preference: 'problem_solving',
        has_basic_profile: true,
        is_complete: true,
      },
      loading: false,
    };

    renderRoutes('/profile/setup');

    expect(screen.getByText('Dashboard screen')).toBeInTheDocument();
  });
});
