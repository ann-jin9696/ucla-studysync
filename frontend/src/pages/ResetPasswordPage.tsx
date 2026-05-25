import { Alert, Button, Form, Input } from 'antd';
import { LockKey } from '@phosphor-icons/react';
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api';
import { useAuth } from '../components/AuthProvider';
import { AuthShell } from './AuthShell';

type ResetPasswordValues = {
  password: string;
};

export function ResetPasswordPage() {
  const { setAuthenticatedUser } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleFinish(values: ResetPasswordValues) {
    setSubmitting(true);
    setError(null);
    try {
      const response = await authApi.confirmPasswordReset({
        token,
        password: values.password,
      });
      setAuthenticatedUser(response.user);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to reset password.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      eyebrow="New password"
      title="Choose a fresh password."
      subtitle="Reset links expire quickly, so save the new password now."
      switchPrompt="Back to"
      switchLabel="Log in"
      switchTo="/login"
    >
      <Form layout="vertical" onFinish={handleFinish} className="auth-form">
        {error && <Alert type="error" message={error} showIcon />}
        {!token && (
          <Alert
            type="error"
            message="Reset token missing"
            description="Request a new password recovery email from the login page."
            showIcon
          />
        )}
        <Form.Item
          label="New password"
          name="password"
          rules={[
            { required: true, message: 'Please enter a new password.' },
            { min: 8, message: 'Use at least 8 characters.' },
          ]}
        >
          <Input.Password
            autoComplete="new-password"
            prefix={<LockKey size={18} weight="duotone" />}
            placeholder="At least 8 characters"
            disabled={!token}
          />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={submitting} disabled={!token}>
          Reset password
        </Button>
      </Form>
    </AuthShell>
  );
}
