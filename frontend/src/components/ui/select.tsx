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
        <label htmlFor={selectId} className="mb-2 block text-sm font-medium text-slate-300">
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
            'flex min-h-11 w-full items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950 py-2.5 ps-3.5 pe-3 text-sm text-slate-200 transition outline-none',
            'hover:border-slate-700',
            'focus:border-cyan-400/50 focus:ring-2 focus:ring-cyan-400/10',
            'data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50',
            'data-[placeholder]:text-slate-600',
            error && 'border-red-400/50 focus:border-red-400 focus:ring-red-400/10',
            className,
          )}
        >
          <SelectPrimitive.Value placeholder={placeholder} />

          <SelectPrimitive.Icon asChild>
            <svg
              aria-hidden="true"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 group-data-[state=open]:rotate-180"
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
              'trd-select-content z-100 max-h-72 w-(--radix-select-trigger-width) origin-(--radix-select-content-transform-origin) overflow-hidden rounded-xl border border-slate-700 bg-slate-950 p-1 text-slate-200 shadow-2xl shadow-black/40',
              contentClassName,
            )}
          >
            <SelectPrimitive.ScrollUpButton className="flex h-7 items-center justify-center text-slate-500">
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

            <SelectPrimitive.ScrollDownButton className="flex h-7 items-center justify-center text-slate-500">
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
          className={cn('mt-2 text-xs', error ? 'text-red-300' : 'text-slate-500')}
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
      'relative flex min-h-10 cursor-pointer items-center rounded-lg py-2.5 ps-3 pe-9 text-sm text-slate-300 transition outline-none select-none',
      'data-[highlighted]:bg-cyan-400/10 data-[highlighted]:text-cyan-200',
      'data-[state=checked]:text-cyan-300',
      'data-[disabled]:pointer-events-none data-[disabled]:opacity-40',
      className,
    )}
    {...props}
  >
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>

    <SelectPrimitive.ItemIndicator className="absolute end-3 flex items-center text-cyan-400">
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
