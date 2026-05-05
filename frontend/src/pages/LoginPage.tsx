import { Alert, Button, Form, Input } from 'antd';
import { EnvelopeSimple, LockKey } from '@phosphor-icons/react';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../components/AuthProvider';
import { AuthShell } from './AuthShell';

type LoginValues = {
  email: string;
  password: string;
};

type LocationState = {
  from?: {
    pathname?: string;
  };
};

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as LocationState | null)?.from?.pathname ?? '/dashboard';

  async function handleFinish(values: LoginValues) {
    setError(null);
    setSubmitting(true);
    try {
      await login(values);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to log in.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Welcome back"
      title="Pick up where your study circle left off."
      subtitle="Log in to return to your dashboard and keep the group project momentum moving."
      switchPrompt="New to StudySync?"
      switchLabel="Create an account"
      switchTo="/signup"
    >
      <Form layout="vertical" onFinish={handleFinish} className="auth-form">
        {error && <Alert type="error" message={error} showIcon />}
        <Form.Item
          label="UCLA email"
          name="email"
          rules={[
            { required: true, message: 'Please enter your email.' },
            { type: 'email', message: 'Please enter a valid email address.' },
          ]}
        >
          <Input prefix={<EnvelopeSimple size={18} weight="duotone" />} placeholder="you@g.ucla.edu" />
        </Form.Item>
        <Form.Item
          label="Password"
          name="password"
          rules={[{ required: true, message: 'Please enter your password.' }]}
        >
          <Input.Password prefix={<LockKey size={18} weight="duotone" />} placeholder="Your password" />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={submitting}>
          Log in
        </Button>
      </Form>
    </AuthShell>
  );
}
