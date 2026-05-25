import { Alert, Button, Form, Input } from 'antd';
import { EnvelopeSimple, LockKey, UserCircle } from '@phosphor-icons/react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../components/AuthProvider';
import { AuthShell } from './AuthShell';

type SignupValues = {
  full_name: string;
  email: string;
  password: string;
};

export function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleFinish(values: SignupValues) {
    setError(null);
    setSubmitting(true);
    try {
      await signup(values);
      navigate('/profile/setup', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create account.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Start with your UCLA email"
      title="Make study feel a little brighter."
      subtitle="Create your StudySync account now, then add your current courses to unlock your dashboard."
      switchPrompt="Already have an account?"
      switchLabel="Log in"
      switchTo="/login"
    >
      <Form layout="vertical" onFinish={handleFinish} className="auth-form">
        {error && <Alert type="error" message={error} showIcon />}
        <Form.Item
          label="Full name"
          name="full_name"
          rules={[{ required: true, message: 'Please enter your full name.' }]}
        >
          <Input
            autoComplete="name"
            prefix={<UserCircle size={18} weight="duotone" />}
            placeholder="Sunny Bruin"
          />
        </Form.Item>
        <Form.Item
          label="UCLA email"
          name="email"
          rules={[
            { required: true, message: 'Please enter your UCLA email.' },
            { type: 'email', message: 'Please enter a valid email address.' },
            {
              validator: (_, value) => {
                if (!value) return Promise.resolve();
                const domain = String(value).trim().toLowerCase().split('@')[1] ?? '';
                return domain === 'ucla.edu' || domain.endsWith('.ucla.edu')
                  ? Promise.resolve()
                  : Promise.reject(new Error('Use your UCLA email address.'));
              },
            },
          ]}
        >
          <Input
            autoComplete="email"
            prefix={<EnvelopeSimple size={18} weight="duotone" />}
            placeholder="you@g.ucla.edu"
          />
        </Form.Item>
        <Form.Item
          label="Password"
          name="password"
          rules={[
            { required: true, message: 'Please create a password.' },
            { min: 8, message: 'Use at least 8 characters.' },
          ]}
        >
          <Input.Password
            autoComplete="new-password"
            prefix={<LockKey size={18} weight="duotone" />}
            placeholder="At least 8 characters"
          />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={submitting}>
          Create account
        </Button>
      </Form>
    </AuthShell>
  );
}
