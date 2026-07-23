import {
  createContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import keycloak from './keycloak';

export interface AuthUser {
  sub: string;
  preferred_username: string;
  name: string;
  email: string;
  department_code: string;
  department_name: string;
  roles: string[];
}

export interface AuthContextValue {
  authenticated: boolean;
  user: AuthUser | null;
  token: string | null;
  login: () => void;
  logout: () => void;
  hasRole: (role: string) => boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

function parseUser(token: string): AuthUser {
  const payload = JSON.parse(atob(token.split('.')[1]));
  const roles: string[] =
    payload.resource_access?.['shouhou-gongdan-api']?.roles ?? [];
  return {
    sub: payload.sub ?? '',
    preferred_username: payload.preferred_username ?? '',
    name: payload.name ?? '',
    email: payload.email ?? '',
    department_code: payload.department_code ?? '',
    department_name: payload.department_name ?? '',
    roles,
  };
}

interface Props {
  children: ReactNode;
}

export function KeycloakProvider({ children }: Props) {
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
            setUser(parseUser(keycloak.token));
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
      })
      .then((auth) => {
        if (auth && keycloak.token) {
          setAuthenticated(true);
          setToken(keycloak.token);
          setUser(parseUser(keycloak.token));
          startTokenRefresh();
        }
      })
      .catch((err) => {
        console.error('Keycloak init failed:', err);
      });
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
    authenticated,
    user,
    token,
    login,
    logout,
    hasRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
