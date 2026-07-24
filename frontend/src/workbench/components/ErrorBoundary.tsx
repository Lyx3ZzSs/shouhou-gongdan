import { Component, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ErrorBoundaryProps {
  /** Panel name shown in the fallback UI */
  panelName: string;
  /** Called when the user clicks "重试" (retry) */
  onRetry?: () => void;
  /** Optional className for the wrapper */
  className?: string;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error Boundary that isolates each panel independently.
 * If a panel throws during render, only that panel shows a fallback UI
 * — other panels continue to function normally.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error(
      `[ErrorBoundary] ${this.props.panelName} crashed:`,
      error,
      '\nComponent stack:',
      errorInfo.componentStack,
    );
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    this.props.onRetry?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className={cn(
            'flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center',
            this.props.className,
          )}
          role="alert"
        >
          <AlertTriangle className="h-8 w-8 text-destructive" />
          <div>
            <p className="text-sm font-medium text-foreground">
              {this.props.panelName} 加载失败
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {this.state.error?.message || '未知错误'}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={this.handleRetry}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            重试
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
