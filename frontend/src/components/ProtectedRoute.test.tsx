import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ProtectedRoute } from './ProtectedRoute';

let authState = {
  user: null,
  loading: false,
};

vi.mock('./AuthProvider', () => ({
  useAuth: () => authState,
}));

describe('ProtectedRoute', () => {
  it('redirects logged-out users to login', () => {
    authState = { user: null, loading: false };

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <p>Private dashboard</p>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<p>Login screen</p>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText('Login screen')).toBeInTheDocument();
  });
});
