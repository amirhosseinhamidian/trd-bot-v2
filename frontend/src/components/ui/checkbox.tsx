import { forwardRef, type InputHTMLAttributes, type ReactNode, useId } from 'react';

import { cn } from '@/lib/utils/cn';

export type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  containerClassName?: string;
  description?: ReactNode;
  label: ReactNode;
};

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, containerClassName, description, disabled, id, label, ...props }, ref) => {
    const generatedId = useId();
    const checkboxId = id ?? generatedId;

    return (
      <label
        htmlFor={checkboxId}
        className={cn(
          'inline-flex cursor-pointer items-start gap-3',
          disabled && 'cursor-not-allowed opacity-50',
          containerClassName,
        )}
      >
        <input
          ref={ref}
          id={checkboxId}
          type="checkbox"
          disabled={disabled}
          className={cn(
            'mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded border-app-border bg-app-surface accent-app-accent',
            'focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none',
            'disabled:cursor-not-allowed',
            className,
          )}
          {...props}
        />

        <span>
          <span className="block text-sm font-medium text-app-foreground">{label}</span>

          {description ? (
            <span className="mt-1 block text-xs leading-5 text-app-muted">{description}</span>
          ) : null}
        </span>
      </label>
    );
  },
);

Checkbox.displayName = 'Checkbox';
