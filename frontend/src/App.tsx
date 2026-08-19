import { lazy, Suspense, useState } from 'react';
import { motion } from 'framer-motion';
import { Loader2, LogIn, ShieldCheck } from 'lucide-react';
import { KeycloakProvider, MockAuthProvider } from './auth';
import { useAuth } from './auth';
import { authEnabled } from './auth/keycloak';
import type { PlatformView } from '@/components/PlatformNav';

const ReviewStats = lazy(() => import('./stats/ReviewStats'));
const WorkOrderModule = lazy(() => import('./modules/WorkOrderModule'));

function AppContent() {
  const { initializing, authenticated, login } = useAuth();
  const [view, setView] = useState<PlatformView>('ledger');
  const navigate = (next: PlatformView) => setView(next === 'stats' ? 'stats' : 'ledger');

  if (initializing) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-app">
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
          className="relative flex flex-col items-center gap-4"
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20">
            <ShieldCheck className="h-7 w-7 text-primary" />
          </div>
          <h1 className="text-xl font-bold tracking-tight">
            售后工单审核工作台
          </h1>
          <Loader2 className="h-5 w-5 text-muted-foreground animate-spin" />
        </motion.div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-app">
        <motion.div
          initial={{ opacity: 0, y: 20, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="relative"
        >
          <div className="max-w-sm rounded-xl border border-border bg-card p-10 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20 mx-auto mb-6">
              <ShieldCheck className="h-7 w-7 text-primary" />
            </div>
            <h1 className="mb-2 text-xl font-bold tracking-tight">
              售后工单审核工作台
            </h1>
            <p className="text-muted-foreground mb-8 text-sm">请登录后使用</p>
            <button
              onClick={login}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              <LogIn className="h-4 w-4" />
              统一身份认证登录
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  return view === 'stats' ? (
    <Suspense fallback={<div className="flex h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin" /></div>}>
      <ReviewStats onNavigate={navigate} />
    </Suspense>
  ) : (
    <Suspense fallback={<div className="flex h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin" /></div>}>
      <WorkOrderModule view="ledger" onNavigate={navigate} onReview={() => undefined} />
    </Suspense>
  );
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
