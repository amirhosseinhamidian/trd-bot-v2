'use client';

import {
  forwardRef,
  type ComponentPropsWithoutRef,
  type ComponentRef,
  type ReactNode,
  useId,
} from 'react';
import { Select as SelectPrimitive } from 'radix-ui';

import { cn } from '@/lib/utils/cn';

type SelectRootProps = ComponentPropsWithoutRef<typeof SelectPrimitive.Root>;

export type SelectProps = Omit<SelectRootProps, 'children'> & {
  children: ReactNode;
  className?: string;
  containerClassName?: string;
  contentClassName?: string;
  error?: string;
  hint?: string;
  id?: string;
  label?: string;
  placeholder?: string;
};

export function Select({
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
  placeholder,
  ...props
}: SelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const messageId = `${selectId}-message`;

  return (
    <div className={cn('w-full', containerClassName)}>
      {label ? (
        <label htmlFor={selectId} className="mb-2 block text-sm font-medium text-app-foreground">
          {label}
        </label>
      ) : null}

      <SelectPrimitive.Root dir={dir} disabled={disabled} {...props}>
        <SelectPrimitive.Trigger
          id={selectId}
          aria-invalid={error ? true : undefined}
          aria-describedby={error || hint ? messageId : undefined}
          dir={dir}
          className={cn(
            'flex min-h-11 w-full min-w-0 items-center justify-between gap-3 overflow-hidden rounded-xl border border-app-border bg-app-surface py-2.5 ps-3.5 pe-3 text-sm text-app-foreground transition outline-none',
            'hover:bg-app-hover',
            'focus:border-app-accent-border focus:ring-2 focus:ring-app-accent-soft',
            'data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50',
            'data-[placeholder]:text-app-subtle',
            error && 'border-red-500/50 focus:border-red-500 focus:ring-red-500/10',
            className,
          )}
        >
          <span data-slot="select-value" className="min-w-0 flex-1 truncate text-start">
            <SelectPrimitive.Value placeholder={placeholder} />
          </span>

          <SelectPrimitive.Icon asChild>
            <svg
              aria-hidden="true"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="h-4 w-4 shrink-0 text-app-muted transition-transform duration-200 group-data-[state=open]:rotate-180"
            >
              <path
                fillRule="evenodd"
                d="M5.22 7.22a.75.75 0 0 1 1.06 0L10 10.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 8.28a.75.75 0 0 1 0-1.06Z"
                clipRule="evenodd"
              />
            </svg>
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>

        <SelectPrimitive.Portal>
          <SelectPrimitive.Content
            position="popper"
            side="bottom"
            dir={dir}
            align="start"
            sideOffset={6}
            avoidCollisions={false}
            className={cn(
              'trd-select-content z-100 max-h-72 w-(--radix-select-trigger-width) origin-(--radix-select-content-transform-origin) overflow-hidden rounded-xl border border-app-border bg-app-surface p-1 text-app-foreground shadow-2xl shadow-black/20',
              contentClassName,
            )}
          >
            <SelectPrimitive.ScrollUpButton className="flex h-7 items-center justify-center text-app-muted">
              <svg
                aria-hidden="true"
                viewBox="0 0 20 20"
                fill="currentColor"
                className="h-4 w-4 rotate-180"
              >
                <path
                  fillRule="evenodd"
                  d="M5.22 7.22a.75.75 0 0 1 1.06 0L10 10.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 8.28a.75.75 0 0 1 0-1.06Z"
                  clipRule="evenodd"
                />
              </svg>
            </SelectPrimitive.ScrollUpButton>

            <SelectPrimitive.Viewport className="max-h-64">{children}</SelectPrimitive.Viewport>

            <SelectPrimitive.ScrollDownButton className="flex h-7 items-center justify-center text-app-muted">
              <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path
                  fillRule="evenodd"
                  d="M5.22 7.22a.75.75 0 0 1 1.06 0L10 10.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 8.28a.75.75 0 0 1 0-1.06Z"
                  clipRule="evenodd"
                />
              </svg>
            </SelectPrimitive.ScrollDownButton>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>

      {error || hint ? (
        <p
          id={messageId}
          role={error ? 'alert' : undefined}
          className={cn('mt-2 text-xs', error ? 'text-red-500' : 'text-app-muted')}
        >
          {error ?? hint}
        </p>
      ) : null}
    </div>
  );
}

export type SelectOptionProps = ComponentPropsWithoutRef<typeof SelectPrimitive.Item>;

export const SelectOption = forwardRef<
  ComponentRef<typeof SelectPrimitive.Item>,
  SelectOptionProps
>(({ children, className, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      'relative flex min-h-10 min-w-0 cursor-pointer items-center overflow-hidden rounded-lg py-2.5 ps-3 pe-9 text-sm text-app-foreground transition outline-none select-none',
      'data-[highlighted]:bg-app-accent-soft data-[highlighted]:text-app-accent',
      'data-[state=checked]:text-app-accent',
      'data-[disabled]:pointer-events-none data-[disabled]:opacity-40',
      className,
    )}
    {...props}
  >
    <SelectPrimitive.ItemText className="block min-w-0 truncate">
      {children}
    </SelectPrimitive.ItemText>

    <SelectPrimitive.ItemIndicator className="absolute end-3 flex items-center text-app-accent">
      <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
        <path
          fillRule="evenodd"
          d="M16.704 5.29a1 1 0 0 1 .006 1.414l-7.25 7.31a1 1 0 0 1-1.42 0L3.29 9.224A1 1 0 0 1 4.71 7.81l4.04 4.072 6.54-6.586a1 1 0 0 1 1.414-.006Z"
          clipRule="evenodd"
        />
      </svg>
    </SelectPrimitive.ItemIndicator>
  </SelectPrimitive.Item>
));

SelectOption.displayName = 'SelectOption';
