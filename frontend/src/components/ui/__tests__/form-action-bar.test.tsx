import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Button } from '@/components/ui/button';
import { FormActionBar } from '@/components/ui/form-action-bar';

describe('FormActionBar', () => {
  it('stacks actions on mobile and allows them to wrap on wider viewports', () => {
    render(
      <FormActionBar data-testid="actions">
        <Button>Apply filters</Button>
        <Button variant="secondary">Reset</Button>
      </FormActionBar>,
    );

    expect(screen.getByTestId('actions')).toHaveClass(
      'flex-col',
      'sm:flex-row',
      'sm:flex-wrap',
      '[&>button]:w-full',
      'sm:[&>button]:w-auto',
    );
  });

  it('keeps a primary action above mobile navigation without remaining sticky on desktop', () => {
    render(
      <FormActionBar data-testid="actions" stickyOnMobile>
        <Button>Run experiment</Button>
      </FormActionBar>,
    );

    expect(screen.getByTestId('actions')).toHaveClass(
      'sticky',
      'bottom-[4.75rem]',
      'md:static',
      'md:border-0',
    );
  });
});
