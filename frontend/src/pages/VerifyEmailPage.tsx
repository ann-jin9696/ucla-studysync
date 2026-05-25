import { Alert, Button } from 'antd';
import { CheckCircle, EnvelopeSimple } from '@phosphor-icons/react';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api';
import { useAuth } from '../components/AuthProvider';
import { AuthShell } from './AuthShell';

export function VerifyEmailPage() {
  const { setAuthenticatedUser, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<'idle' | 'confirming' | 'confirmed'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const token = searchParams.get('token');

  useEffect(() => {
    if (!token || status !== 'idle') return;

    async function confirmToken() {
      setStatus('confirming');
      setError(null);
      try {
        const response = await authApi.confirmEmailVerification(token ?? '');
        setAuthenticatedUser(response.user);
        setStatus('confirmed');
      } catch (err) {
        setStatus('idle');
        setError(err instanceof Error ? err.message : 'Could not verify email.');
      }
    }

    confirmToken();
  }, [setAuthenticatedUser, status, token]);

  async function handleResend() {
    setResending(true);
    setError(null);
    try {
      await authApi.resendEmailVerification();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not resend verification email.');
    } finally {
      setResending(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Email verification"
      title="Confirm your UCLA inbox."
      subtitle="StudySync uses email verification before opening group matching and shared workspaces."
      switchPrompt="Already verified?"
      switchLabel="Continue"
      switchTo="/dashboard"
    >
      <div className="auth-action-stack">
        {error && <Alert type="error" message={error} showIcon />}
        {status === 'confirmed' || user?.email_verified ? (
          <Alert
            type="success"
            showIcon
            icon={<CheckCircle size={20} weight="duotone" />}
            message="Email verified"
            description="Your StudySync account is ready."
          />
        ) : (
          <Alert
            type="info"
            showIcon
            icon={<EnvelopeSimple size={20} weight="duotone" />}
            message="Check your email"
            description="Open the verification link we sent to your UCLA address."
          />
        )}
        {status === 'confirmed' || user?.email_verified ? (
          <Button
            type="primary"
            block
            onClick={() => navigate('/profile/setup', { replace: true })}
          >
            Continue
          </Button>
        ) : (
          <Button block loading={resending} onClick={handleResend}>
            Resend verification email
          </Button>
        )}
      </div>
    </AuthShell>
  );
}
