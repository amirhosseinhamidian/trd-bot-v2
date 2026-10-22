'use client';

import {
  forwardRef,
  type AriaAttributes,
  type ChangeEventHandler,
  type ComponentPropsWithoutRef,
  type ReactNode,
  useId,
} from 'react';

import { cn } from '@/lib/utils/cn';

type NativeSelectProps = ComponentPropsWithoutRef<'select'>;

export type SelectProps = Omit<NativeSelectProps, 'children' | 'onChange'> &
  Pick<AriaAttributes, 'aria-describedby' | 'aria-invalid'> & {
    children: ReactNode;
    className?: string;
    containerClassName?: string;
    contentClassName?: string;
    error?: string;
    hint?: string;
    id?: string;
    label?: string;
    onChange?: ChangeEventHandler<HTMLSelectElement>;
    onValueChange?: (value: string) => void;
    placeholder?: string;
  };

/**
 * Browser-native select with the shared application field styling.
 *
 * Keeping the interaction native makes the control available before React
 * hydration completes and delegates keyboard, touch, and popup behavior to
 * the browser. `onValueChange` preserves the existing application-facing API.
 */
export function Select({
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  children,
  className,
  containerClassName,
  contentClassName,
  dir,
  disabled,
  error,
  hint,
  id,
  label,
  onChange,
  onValueChange,
  placeholder,
  ...props
}: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const messageId = `${selectId}-message`;
  const describedBy =
    [ariaDescribedBy, error || hint ? messageId : null].filter(Boolean).join(' ') || undefined;

  return (
    <div className={cn('w-full', containerClassName)}>
      {label ? (
        <label htmlFor={selectId} className="mb-2 block text-sm font-medium text-app-foreground">
          {label}
        </label>
      ) : null}

      <div className={cn('relative', contentClassName)}>
        <select
          id={selectId}
          aria-invalid={error ? true : ariaInvalid}
          aria-describedby={describedBy}
          dir={dir}
          disabled={disabled}
          onChange={(event) => {
            onChange?.(event);
            onValueChange?.(event.currentTarget.value);
          }}
          className={cn(
            'min-h-11 w-full min-w-0 appearance-none rounded-xl border border-app-control-border bg-app-surface py-2.5 ps-3.5 pe-10 text-sm text-app-foreground transition-colors outline-none',
            'hover:border-app-muted hover:bg-app-hover',
            'focus:border-app-accent focus:ring-2 focus:ring-app-accent-soft',
            'disabled:cursor-not-allowed disabled:bg-app-surface-muted disabled:text-app-muted disabled:opacity-70',
            error &&
              'border-app-danger hover:border-app-danger focus:border-app-danger focus:ring-app-danger-soft',
            className,
          )}
          {...props}
        >
          {placeholder ? (
            <option value="" disabled>
              {placeholder}
            </option>
          ) : null}
          {children}
        </select>

        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="pointer-events-none absolute end-3 top-1/2 h-4 w-4 -translate-y-1/2 text-app-muted"
        >
          <path
            fillRule="evenodd"
            d="M5.22 7.22a.75.75 0 0 1 1.06 0L10 10.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 8.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </div>

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
}

export type SelectOptionProps = ComponentPropsWithoutRef<'option'>;

export const SelectOption = forwardRef<HTMLOptionElement, SelectOptionProps>(
  ({ children, className, ...props }, ref) => (
    <option ref={ref} className={cn('bg-app-surface text-app-foreground', className)} {...props}>
      {children}
    </option>
  ),
);

SelectOption.displayName = 'SelectOption';
