import { Spin } from 'antd';
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useProfile } from './ProfileProvider';

type ProfileGateProps = {
  children: ReactNode;
  requireBasicProfile?: boolean;
  redirectCompleteSetup?: boolean;
};

export function ProfileGate({
  children,
  requireBasicProfile = false,
  redirectCompleteSetup = false,
}: ProfileGateProps) {
  const { profile, loading } = useProfile();
  const location = useLocation();

  if (loading) {
    return (
      <main className="screen-center">
        <Spin size="large" />
      </main>
    );
  }

  if (redirectCompleteSetup && profile?.is_complete) {
    return <Navigate to="/dashboard" replace />;
  }

  if (requireBasicProfile && !profile?.has_basic_profile) {
    return <Navigate to="/profile/setup" replace state={{ from: location }} />;
  }

  return children;
}
