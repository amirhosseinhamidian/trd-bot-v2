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
  primary:
    'bg-app-accent text-app-background hover:bg-app-accent-hover focus-visible:ring-app-accent',
  secondary:
    'border border-app-control-border bg-app-surface text-app-foreground hover:border-app-muted hover:bg-app-hover focus-visible:ring-app-accent',
  ghost:
    'bg-transparent text-app-muted hover:bg-app-hover hover:text-app-foreground focus-visible:ring-app-accent',
  danger:
    'border border-app-danger-border bg-app-danger-soft text-app-danger hover:border-app-danger focus-visible:ring-app-danger',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'min-h-11 px-3 py-2 text-xs',
  md: 'min-h-11 px-4 py-2.5 text-sm',
  lg: 'min-h-12 px-5 py-3 text-base',
  icon: 'h-11 w-11 p-0',
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
          'inline-flex max-w-full min-w-0 items-center justify-center gap-2 rounded-xl font-semibold transition-colors focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none disabled:pointer-events-none disabled:opacity-60',
          variants[variant],
          sizes[size],
          fullWidth && 'w-full',
          className,
        )}
        {...props}
      >
        {isLoading ? <Spinner size="sm" /> : null}
        <span className="max-w-full min-w-0 text-center break-words">
          {isLoading && loadingText ? loadingText : children}
        </span>
      </button>
    );
  },
);

Button.displayName = 'Button';
