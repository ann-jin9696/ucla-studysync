import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { profileApi } from '../api';
import type { Profile, ProfileInput } from '../api';
import { useAuth } from './AuthProvider';

type ProfileContextValue = {
  profile: Profile | null;
  loading: boolean;
  error: string | null;
  refreshProfile: () => Promise<void>;
  saveProfile: (input: ProfileInput) => Promise<Profile>;
};

const ProfileContext = createContext<ProfileContextValue | undefined>(undefined);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshProfile() {
    if (!user) {
      setProfile(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await profileApi.me();
      setProfile(response);
    } catch (err) {
      setProfile(null);
      setError(err instanceof Error ? err.message : 'Could not load profile.');
    } finally {
      setLoading(false);
    }
  }

  async function saveProfile(input: ProfileInput) {
    const response = await profileApi.update(input);
    setProfile(response);
    return response;
  }

  useEffect(() => {
    if (authLoading) {
      return;
    }
    void refreshProfile();
  }, [authLoading, user?.id]);

  const value = useMemo(
    () => ({ profile, loading: authLoading || loading, error, refreshProfile, saveProfile }),
    [profile, authLoading, loading, error],
  );

  return <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>;
}

export function useProfile() {
  const context = useContext(ProfileContext);
  if (!context) {
    throw new Error('useProfile must be used inside ProfileProvider');
  }
  return context;
}
