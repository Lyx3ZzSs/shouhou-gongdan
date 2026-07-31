import { createContext, type ReactNode } from 'react';
import type { AuthContextValue } from './KeycloakProvider';

/** AUTH_ENABLED=false 时使用的默认开发用户（拥有全部角色） */
const MOCK_USER = {
  sub: 'dev-user',
  preferred_username: 'dev',
  name: '开发用户',
  email: 'dev@localhost',
  department_code: 'DEV',
  department_name: '开发部',
  roles: ['agent_admin', 'agent_manager', 'agent_user'],
};

export const mockAuthValue: AuthContextValue = {
  initializing: false,
  authenticated: true,
  user: MOCK_USER,
  token: 'dev-token',
  login: () => {},
  logout: () => {},
  hasRole: (_role: string) => true,
};

export const MockAuthContext = createContext<AuthContextValue>(mockAuthValue);

export function MockAuthProvider({ children }: { children: ReactNode }) {
  if (import.meta.env.PROD) {
    throw new Error(
      'MockAuthProvider 不应在生产环境中使用。请检查 VITE_AUTH_ENABLED 配置。',
    );
  }
  return (
    <MockAuthContext.Provider value={mockAuthValue}>
      {children}
    </MockAuthContext.Provider>
  );
}
