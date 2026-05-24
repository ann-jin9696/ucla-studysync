import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { describe, expect, it, vi } from 'vitest';
import type { Profile, ProfileInput } from '../api';
import { ProfileForm } from './ProfileForm';

const apiMocks = vi.hoisted(() => ({
  courseCodes: vi.fn(async (search = '') => ({
    options: search.toLowerCase().startsWith('c') ? ['CS35L', 'CS111'] : [],
  })),
}));

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    profileApi: {
      ...actual.profileApi,
      courseCodes: apiMocks.courseCodes,
    },
  };
});

const emptyProfile: Profile = {
  courses: [],
  has_basic_profile: false,
  is_complete: false,
  created_at: null,
  updated_at: null,
};

function renderProfileForm() {
  return render(
    <ConfigProvider>
      <ProfileForm
        profile={emptyProfile}
        onSubmit={vi.fn(async (_input: ProfileInput) => undefined)}
        submitLabel="Save profile"
      />
    </ConfigProvider>,
  );
}

describe('ProfileForm', () => {
  it('shows existing course code matches while typing', async () => {
    const user = userEvent.setup();
    renderProfileForm();

    await user.type(screen.getByRole('combobox', { name: 'Course code' }), 'cs');

    await waitFor(() => {
      expect(apiMocks.courseCodes).toHaveBeenCalledWith('cs');
    });
    expect(await screen.findAllByText('CS35L')).not.toHaveLength(0);
    expect(screen.queryByText(/already exists/)).not.toBeInTheDocument();
  });
});
