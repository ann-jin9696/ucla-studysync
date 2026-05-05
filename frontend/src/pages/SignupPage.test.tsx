import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { SignupPage } from './SignupPage';

const signup = vi.fn();

vi.mock('../components/AuthProvider', () => ({
  useAuth: () => ({ signup }),
}));

function renderSignup() {
  return render(
    <ConfigProvider>
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>
    </ConfigProvider>,
  );
}

describe('SignupPage', () => {
  it('shows validation for non-UCLA emails before submitting', async () => {
    renderSignup();

    fireEvent.change(screen.getByPlaceholderText('Sunny Bruin'), {
      target: { value: 'Test Bruin' },
    });
    fireEvent.change(screen.getByPlaceholderText('you@g.ucla.edu'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('At least 8 characters'), {
      target: { value: 'classroom123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText('Use your UCLA email address.')).toBeInTheDocument();
    });
    expect(signup).not.toHaveBeenCalled();
  });
});
