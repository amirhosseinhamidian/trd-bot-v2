import { forwardRef, type InputHTMLAttributes, type ReactNode, useId } from 'react';

import { cn } from '@/lib/utils/cn';

export type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  containerClassName?: string;
  description?: ReactNode;
  label: ReactNode;
};

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  (
    {
      'aria-describedby': ariaDescribedBy,
      className,
      containerClassName,
      description,
      disabled,
      id,
      label,
      ...props
    },
    ref,
  ) => {
    const generatedId = useId();
    const checkboxId = id ?? generatedId;
    const descriptionId = `${checkboxId}-description`;
    const describedBy =
      [ariaDescribedBy, description ? descriptionId : null].filter(Boolean).join(' ') || undefined;

    return (
      <div
        className={cn(
          'inline-flex items-start gap-3',
          disabled && 'cursor-not-allowed opacity-60',
          containerClassName,
        )}
      >
        <input
          ref={ref}
          id={checkboxId}
          type="checkbox"
          disabled={disabled}
          aria-describedby={describedBy}
          className={cn(
            'mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border border-app-control-border bg-app-surface accent-app-accent hover:border-app-muted',
            'focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none',
            'disabled:cursor-not-allowed',
            className,
          )}
          {...props}
        />

        <span>
          <label
            htmlFor={checkboxId}
            className={cn(
              'block cursor-pointer text-sm font-medium text-app-foreground',
              disabled && 'cursor-not-allowed',
            )}
          >
            {label}
          </label>

          {description ? (
            <span id={descriptionId} className="mt-1 block text-xs leading-5 text-app-muted">
              {description}
            </span>
          ) : null}
        </span>
      </div>
    );
  },
);

Checkbox.displayName = 'Checkbox';
