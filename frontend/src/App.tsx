import { lazy, Suspense, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldCheck, LogIn, Loader2 } from 'lucide-react';
import { KeycloakProvider, MockAuthProvider } from './auth';
import { useAuth } from './auth';
import { authEnabled } from './auth/keycloak';
import { viewTransition } from '@/lib/animations';

type View = 'workbench' | 'stats';
const ReviewStats = lazy(() => import('./stats/ReviewStats'));
const ReviewWorkbench = lazy(() => import('./workbench/ReviewWorkbench'));

function AppContent() {
  const { initializing, authenticated, login } = useAuth();
  const [view, setView] = useState<View>('workbench');

  if (initializing) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-app">
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-primary/5 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-primary/3 blur-3xl" />
        </div>
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
          className="relative flex flex-col items-center gap-4"
        >
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20">
            <ShieldCheck className="h-7 w-7 text-primary" />
          </div>
          <h1 className="text-xl font-bold tracking-tight bg-gradient-to-b from-foreground to-foreground/70 bg-clip-text text-transparent">
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
        {/* Ambient background */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-primary/5 blur-3xl" />
          <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-primary/3 blur-3xl" />
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="relative"
        >
          <div className="bg-card/80 backdrop-blur-xl border border-border/40 shadow-glass-lg rounded-2xl p-10 text-center max-w-sm">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20 mx-auto mb-6">
              <ShieldCheck className="h-7 w-7 text-primary" />
            </div>
            <h1 className="text-xl font-bold tracking-tight mb-2 bg-gradient-to-b from-foreground to-foreground/70 bg-clip-text text-transparent">
              售后工单审核工作台
            </h1>
            <p className="text-muted-foreground mb-8 text-sm">请登录后使用</p>
            <button
              onClick={login}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] shadow-sm shadow-primary/20 font-medium text-sm"
            >
              <LogIn className="h-4 w-4" />
              统一身份认证登录
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <AnimatePresence mode="wait">
      {view === 'stats' ? (
        <Suspense fallback={<div className="flex h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin" /></div>}>
        <motion.div
          key="stats"
          variants={viewTransition}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="h-full"
        >
          <ReviewStats onBack={() => setView('workbench')} />
        </motion.div>
        </Suspense>
      ) : (
        <Suspense fallback={<div className="flex h-screen items-center justify-center"><Loader2 className="h-6 w-6 animate-spin" /></div>}>
        <motion.div
          key="workbench"
          variants={viewTransition}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="h-full"
        >
          <ReviewWorkbench onNavigateStats={() => setView('stats')} />
        </motion.div>
        </Suspense>
      )}
    </AnimatePresence>
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
