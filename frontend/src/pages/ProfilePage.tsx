import { Alert, Button, message } from 'antd';
import { ArrowLeft, SignOut, UserCircle } from '@phosphor-icons/react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../components/AuthProvider';
import { ProfileForm } from '../components/ProfileForm';
import { useProfile } from '../components/ProfileProvider';
import { EMPTY_PROFILE, getMissingProfileSections } from '../profileOptions';
import type { ProfileInput } from '../api';
import studySyncLogo from '../assets/studysync-logo.png';

export function ProfilePage() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { profile, error, saveProfile } = useProfile();
  const [messageApi, contextHolder] = message.useMessage();
  const [submitting, setSubmitting] = useState(false);

  const activeProfile = profile ?? EMPTY_PROFILE;
  const missingSections = useMemo(
    () => getMissingProfileSections(activeProfile),
    [activeProfile],
  );

  async function handleLogout() {
    await logout();
    navigate('/login', { replace: true });
  }

  async function handleSubmit(input: ProfileInput) {
    setSubmitting(true);
    try {
      const savedProfile = await saveProfile(input);
      messageApi.success('Profile saved.');
      if (savedProfile.has_basic_profile) {
        navigate('/dashboard', { replace: true });
      }
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : 'Could not save profile.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="dashboard-page profile-page">
      {contextHolder}
      <nav className="dashboard-nav">
        <div className="brand-cluster compact">
          <div className="brand-mark">
            <img src={studySyncLogo} alt="" />
          </div>
          <div>
            <p className="brand-kicker">StudySync</p>
            <strong>Profile setup</strong>
          </div>
        </div>
        <div className="dashboard-actions">
          <Button icon={<ArrowLeft size={18} weight="bold" />} onClick={() => navigate('/dashboard')}>
            Dashboard
          </Button>
          <Button icon={<SignOut size={18} weight="bold" />} onClick={handleLogout}>
            Logout
          </Button>
        </div>
      </nav>

      <section className="profile-header">
        <div>
          <p className="eyebrow">Study profile</p>
          <h1>Tell StudySync what you are taking.</h1>
          <p>
            Courses unlock your dashboard. Each course offering can keep its own goals,
            pace, and group size for matching.
          </p>
        </div>
        <div className="profile-status-card">
          <UserCircle size={32} weight="duotone" />
          <strong>{activeProfile.is_complete ? 'Complete' : 'Needs details'}</strong>
          <span>
            {activeProfile.has_basic_profile ? 'Dashboard access ready' : 'Courses required'}
          </span>
        </div>
      </section>

      <section className="profile-shell">
        {error && <Alert type="error" message={error} showIcon />}
        {!activeProfile.is_complete && (
          <Alert
            className="profile-reminder"
            showIcon
            type="warning"
            message="Finish your profile"
            description={`Still missing: ${missingSections.join(', ')}.`}
          />
        )}
        <ProfileForm
          profile={activeProfile}
          onSubmit={handleSubmit}
          submitLabel="Save profile"
          submitting={submitting}
        />
      </section>
    </main>
  );
}
