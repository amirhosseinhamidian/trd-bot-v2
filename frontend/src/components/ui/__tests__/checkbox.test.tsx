import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Checkbox } from '@/components/ui/checkbox';

describe('Checkbox', () => {
  it('is label-operable and exposes its description', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <Checkbox
        label="Compare candidate"
        description="Adds this candidate to the comparison set."
        onChange={onChange}
      />,
    );

    const checkbox = screen.getByRole('checkbox', { name: 'Compare candidate' });
    const description = screen.getByText('Adds this candidate to the comparison set.');

    expect(checkbox).toHaveAttribute('aria-describedby', description.id);
    expect(checkbox).toHaveClass(
      'border-app-control-border',
      'accent-app-accent',
      'focus-visible:ring-app-accent',
    );

    await user.click(screen.getByText('Compare candidate'));

    expect(checkbox).toBeChecked();
    expect(onChange).toHaveBeenCalledOnce();
  });

  it('preserves the native disabled contract', () => {
    render(<Checkbox label="Unavailable candidate" disabled />);

    expect(screen.getByRole('checkbox', { name: 'Unavailable candidate' })).toBeDisabled();
  });
});
