import Keycloak from 'keycloak-js';

const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || 'http://10.8.6.32:18080',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'company-dev',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'shouhou-gongdan-web',
});

export default keycloak;
