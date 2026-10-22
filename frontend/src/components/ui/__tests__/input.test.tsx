import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Input } from '@/components/ui/input';

describe('Input', () => {
  it('uses the high-contrast control and focus tokens', () => {
    render(<Input label="Dataset name" placeholder="Example" />);

    expect(screen.getByRole('textbox', { name: 'Dataset name' })).toHaveClass(
      'border-app-control-border',
      'hover:border-app-muted',
      'focus:border-app-accent',
      'focus:ring-app-accent-soft',
    );
  });

  it('connects caller help and validation feedback to the field', () => {
    const { rerender } = render(
      <>
        <p id="external-help">Use a stable identifier.</p>
        <Input label="Dataset name" hint="Shown in the catalog" aria-describedby="external-help" />
      </>,
    );

    const input = screen.getByRole('textbox', { name: 'Dataset name' });
    const hint = screen.getByText('Shown in the catalog');

    expect(input.getAttribute('aria-describedby')?.split(' ')).toEqual(['external-help', hint.id]);

    rerender(<Input label="Dataset name" error="Dataset name is required" />);

    const invalidInput = screen.getByRole('textbox', { name: 'Dataset name' });
    const error = screen.getByRole('alert');

    expect(invalidInput).toHaveAttribute('aria-invalid', 'true');
    expect(invalidInput).toHaveAttribute('aria-describedby', error.id);
    expect(invalidInput).toHaveClass(
      'border-app-danger',
      'focus:border-app-danger',
      'focus:ring-app-danger-soft',
    );
    expect(error).toHaveClass('text-app-danger');
  });
});
