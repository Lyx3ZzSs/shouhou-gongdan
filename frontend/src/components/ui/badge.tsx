import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-lg border px-1.5 py-0.5 text-xs font-medium transition-colors duration-200 whitespace-nowrap backdrop-blur-sm',
  {
    variants: {
      variant: {
        default: 'border-primary/15 bg-primary/8 text-primary',
        secondary: 'border-transparent bg-secondary/70 text-secondary-foreground',
        outline: 'text-foreground border-border/60 bg-background/50',
        success: 'border-success/15 bg-success/8 text-success',
        warning: 'border-warning/20 bg-warning/8 text-warning',
        destructive: 'border-destructive/15 bg-destructive/8 text-destructive',
        muted: 'border-transparent bg-muted/60 text-muted-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
