import { useMemo, useState } from 'react';
import { Alert, Card, message } from 'antd';
import { CheckCircle, UserCircle } from '@phosphor-icons/react';
import type { ProfileInput } from '../api';
import { EMPTY_PROFILE, getMissingProfileSections } from '../profileOptions';
import { ProfileForm } from './ProfileForm';
import { useProfile } from './ProfileProvider';

export function ProfileSetupModule() {
  const { profile, error, saveProfile } = useProfile();
  const [messageApi, contextHolder] = message.useMessage();
  const [submitting, setSubmitting] = useState(false);

  const activeProfile = profile ?? EMPTY_PROFILE;
  const missingSections = useMemo(
    () => getMissingProfileSections(activeProfile),
    [activeProfile],
  );

  async function handleSubmit(input: ProfileInput) {
    setSubmitting(true);
    try {
      await saveProfile(input);
      messageApi.success('Profile saved.');
    } catch (err) {
      messageApi.error(err instanceof Error ? err.message : 'Could not save profile.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="workspace-shell profile-setup-module">
      {contextHolder}
      <div className="workspace-header profile-setup-header">
        <div>
          <p className="eyebrow">Study profile</p>
          <h2>Profile setup</h2>
          <p>Each course offering keeps its own goals, pace, and group size preference.</p>
        </div>
        <Card className="workspace-stat profile-setup-stat">
          {activeProfile.is_complete ? (
            <CheckCircle size={28} weight="duotone" />
          ) : (
            <UserCircle size={28} weight="duotone" />
          )}
          <strong>{activeProfile.is_complete ? 'Done' : `${missingSections.length} left`}</strong>
          <span>
            {activeProfile.has_basic_profile ? 'Ready' : 'Add courses'}
          </span>
        </Card>
      </div>

      <section className="profile-shell profile-setup-shell">
        {error && <Alert type="error" message={error} showIcon />}
        {!activeProfile.is_complete && missingSections.length > 0 && (
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
    </section>
  );
}
