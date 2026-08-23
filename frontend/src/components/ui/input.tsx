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

    return (
      <div className={cn('w-full', containerClassName)}>
        {label ? (
          <label htmlFor={inputId} className="mb-2 block text-sm font-medium text-slate-300">
            {label}
          </label>
        ) : null}

        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : ariaInvalid}
          aria-describedby={error || hint ? messageId : ariaDescribedBy}
          className={cn(
            'min-h-11 w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-sm text-slate-200 transition outline-none placeholder:text-slate-700 focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/10 disabled:cursor-not-allowed disabled:opacity-50',
            error && 'border-red-400/50 focus:border-red-400 focus:ring-red-400/10',
            className,
          )}
          {...props}
        />

        {error || hint ? (
          <p
            id={messageId}
            role={error ? 'alert' : undefined}
            className={cn('mt-2 text-xs', error ? 'text-red-300' : 'text-slate-500')}
          >
            {error ?? hint}
          </p>
        ) : null}
      </div>
    );
  },
);

Input.displayName = 'Input';
