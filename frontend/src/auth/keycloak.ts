import Keycloak from 'keycloak-js';

/** 认证开关：与后端 AUTH_ENABLED 对应，false 时跳过 Keycloak 登录 */
export const authEnabled =
  import.meta.env.VITE_AUTH_ENABLED !== 'false';

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || 'http://10.8.6.32:18080',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'company-dev',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'shouhou-gongdan-web',
});

export default keycloak;
