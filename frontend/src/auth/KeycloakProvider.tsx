import {
  createContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import keycloak from './keycloak';
import { type AuthUser, parseUserFromToken } from './parseUser';

export interface AuthContextValue {
  initializing: boolean;
  authenticated: boolean;
  user: AuthUser | null;
  token: string | null;
  login: () => void;
  logout: () => void;
  hasRole: (role: string) => boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

interface Props {
  children: ReactNode;
}

export function KeycloakProvider({ children }: Props) {
  const [initializing, setInitializing] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const initialized = useRef(false);
  const refreshTimer = useRef<ReturnType<typeof setInterval>>();

  const startTokenRefresh = useCallback(() => {
    if (refreshTimer.current) {
      clearInterval(refreshTimer.current);
    }
    refreshTimer.current = setInterval(() => {
      keycloak
        .updateToken(30)
        .then((refreshed) => {
          if (refreshed && keycloak.token) {
            setToken(keycloak.token);
            setUser(parseUserFromToken(keycloak.token));
          }
        })
        .catch(() => {
          setAuthenticated(false);
          setUser(null);
          setToken(null);
        });
    }, 30_000);
  }, []);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    keycloak
      .init({
        onLoad: 'login-required',
        pkceMethod: 'S256',
        redirectUri: window.location.origin + '/callback',
      })
      .then((auth) => {
        if (auth && keycloak.token) {
          setAuthenticated(true);
          setToken(keycloak.token);
          setUser(parseUserFromToken(keycloak.token));
          startTokenRefresh();
        }
      })
      .catch((err) => {
        console.error('Keycloak init failed:', err);
      })
      .finally(() => {
        setInitializing(false);
      });

    return () => {
      if (refreshTimer.current) {
        clearInterval(refreshTimer.current);
        refreshTimer.current = undefined;
      }
    };
  }, [startTokenRefresh]);

  const login = useCallback(() => {
    keycloak.login({
      redirectUri: window.location.origin + '/callback',
    });
  }, []);

  const logout = useCallback(() => {
    if (refreshTimer.current) {
      clearInterval(refreshTimer.current);
    }
    keycloak.logout({
      redirectUri: window.location.origin + '/',
    });
  }, []);

  const hasRole = useCallback(
    (role: string): boolean => {
      return user?.roles.includes(role) ?? false;
    },
    [user],
  );

  const value: AuthContextValue = {
    initializing,
    authenticated,
    user,
    token,
    login,
    logout,
    hasRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
