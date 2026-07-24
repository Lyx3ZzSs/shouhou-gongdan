import { useContext } from 'react';
import { AuthContext, type AuthContextValue } from './KeycloakProvider';
import { MockAuthContext } from './mockAuth';

export function useAuth(): AuthContextValue {
  const keycloakCtx = useContext(AuthContext);
  if (keycloakCtx) return keycloakCtx;

  const mockCtx = useContext(MockAuthContext);
  if (mockCtx) return mockCtx;

  throw new Error('useAuth must be used within a KeycloakProvider or MockAuthProvider');
}

export type { AuthUser } from './KeycloakProvider';
