import { useContext } from 'react';
import { AuthContext, type AuthContextValue } from './KeycloakProvider';

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within a KeycloakProvider');
  }
  return context;
}

export type { AuthUser } from './KeycloakProvider';
