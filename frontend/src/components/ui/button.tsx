import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';

export type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  fullWidth?: boolean;
  isLoading?: boolean;
  loadingText?: string;
  size?: ButtonSize;
  variant?: ButtonVariant;
};

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-cyan-400 text-slate-950 hover:bg-cyan-300 focus-visible:ring-cyan-500',
  secondary:
    'border border-app-border bg-app-surface text-app-foreground hover:bg-app-hover focus-visible:ring-app-subtle',
  ghost:
    'bg-transparent text-app-muted hover:bg-app-hover hover:text-app-foreground focus-visible:ring-app-subtle',
  danger:
    'border border-red-500/30 bg-red-500/10 text-red-500 hover:bg-red-500/15 focus-visible:ring-red-500',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'min-h-9 px-3 py-2 text-xs',
  md: 'min-h-10 px-4 py-2.5 text-sm',
  lg: 'min-h-12 px-5 py-3 text-base',
  icon: 'h-10 w-10 p-0',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      className,
      disabled,
      fullWidth = false,
      isLoading = false,
      loadingText,
      size = 'md',
      type = 'button',
      variant = 'primary',
      ...props
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || isLoading}
        aria-busy={isLoading}
        className={cn(
          'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50',
          variants[variant],
          sizes[size],
          fullWidth && 'w-full',
          className,
        )}
        {...props}
      >
        {isLoading ? <Spinner size="sm" /> : null}
        <span>{isLoading && loadingText ? loadingText : children}</span>
      </button>
    );
  },
);

Button.displayName = 'Button';
