import keycloak, { authEnabled } from './keycloak';

export interface AuthUser {
  sub: string;
  preferred_username: string;
  name: string;
  email: string;
  department_code: string;
  department_name: string;
  roles: string[];
}

/** 从 JWT token 中解析用户信息 */
export function parseUserFromToken(token: string): AuthUser {
  const base64 = token.split('.')[1]
    .replace(/-/g, '+')
    .replace(/_/g, '/');
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const payload = JSON.parse(new TextDecoder().decode(bytes));
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

/** 获取当前登录用户的显示名称（不依赖 React context，可在 store 中调用） */
export function getCurrentUserName(): string {
  if (!authEnabled) return '开发用户';
  if (!keycloak.token) return '未知用户';
  try {
    return parseUserFromToken(keycloak.token).name || '未知用户';
  } catch {
    return '未知用户';
  }
}
