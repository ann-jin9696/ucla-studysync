import { Alert, Button, Form, Input } from 'antd';
import { EnvelopeSimple } from '@phosphor-icons/react';
import { useState } from 'react';
import { authApi } from '../api';
import { AuthShell } from './AuthShell';

type ForgotPasswordValues = {
  email: string;
};

export function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleFinish(values: ForgotPasswordValues) {
    setSubmitting(true);
    setError(null);
    try {
      await authApi.requestPasswordReset(values);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to send recovery email.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Password recovery"
      title="Get back into StudySync."
      subtitle="Enter your UCLA email and StudySync will send a password reset link."
      switchPrompt="Remembered it?"
      switchLabel="Log in"
      switchTo="/login"
    >
      <Form layout="vertical" onFinish={handleFinish} className="auth-form">
        {error && <Alert type="error" message={error} showIcon />}
        {submitted && (
          <Alert
            type="success"
            message="Recovery email sent"
            description="If that UCLA email has a StudySync account, a reset link is on the way."
            showIcon
          />
        )}
        <Form.Item
          label="UCLA email"
          name="email"
          rules={[
            { required: true, message: 'Please enter your email.' },
            { type: 'email', message: 'Please enter a valid email address.' },
          ]}
        >
          <Input
            autoComplete="email"
            prefix={<EnvelopeSimple size={18} weight="duotone" />}
            placeholder="you@g.ucla.edu"
          />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={submitting}>
          Send recovery email
        </Button>
      </Form>
    </AuthShell>
  );
}
