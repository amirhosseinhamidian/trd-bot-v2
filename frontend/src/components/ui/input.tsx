'use client';

import { forwardRef, type InputHTMLAttributes, useId } from 'react';

import { cn } from '@/lib/utils/cn';

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  containerClassName?: string;
  error?: string;
  hint?: string;
  label?: string;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      'aria-describedby': ariaDescribedBy,
      'aria-invalid': ariaInvalid,
      className,
      containerClassName,
      error,
      hint,
      id,
      label,
      ...props
    },
    ref,
  ) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    const messageId = `${inputId}-message`;
    const describedBy =
      [ariaDescribedBy, error || hint ? messageId : null].filter(Boolean).join(' ') || undefined;

    return (
      <div className={cn('w-full', containerClassName)}>
        {label ? (
          <label htmlFor={inputId} className="mb-2 block text-sm font-medium text-app-foreground">
            {label}
          </label>
        ) : null}

        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : ariaInvalid}
          aria-describedby={describedBy}
          className={cn(
            'min-h-11 w-full rounded-xl border border-app-control-border bg-app-surface px-3.5 py-2.5 text-sm text-app-foreground transition-colors outline-none placeholder:text-app-subtle hover:border-app-muted focus:border-app-accent focus:ring-2 focus:ring-app-accent-soft disabled:cursor-not-allowed disabled:bg-app-surface-muted disabled:text-app-muted disabled:opacity-70',
            error &&
              'border-app-danger hover:border-app-danger focus:border-app-danger focus:ring-app-danger-soft',
            className,
          )}
          {...props}
        />

        {error || hint ? (
          <p
            id={messageId}
            role={error ? 'alert' : undefined}
            className={cn('mt-2 text-xs', error ? 'text-app-danger' : 'text-app-muted')}
          >
            {error ?? hint}
          </p>
        ) : null}
      </div>
    );
  },
);

Input.displayName = 'Input';
