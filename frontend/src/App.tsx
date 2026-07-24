import { KeycloakProvider, MockAuthProvider } from './auth';
import { useAuth } from './auth';
import { authEnabled } from './auth/keycloak';
import { ReviewWorkbench } from './workbench/ReviewWorkbench';

function AppContent() {
  const { authenticated, login } = useAuth();

  if (!authenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">售后工单审核工作台</h1>
          <p className="text-gray-500 mb-6">请登录后使用</p>
          <button
            onClick={login}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            统一身份认证登录
          </button>
        </div>
      </div>
    );
  }

  return <ReviewWorkbench />;
}

function App() {
  if (!authEnabled) {
    return (
      <MockAuthProvider>
        <AppContent />
      </MockAuthProvider>
    );
  }

  return (
    <KeycloakProvider>
      <AppContent />
    </KeycloakProvider>
  );
}

export default App;
