import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Select, SelectOption } from '@/components/ui/select';

describe('Select', () => {
  it('constrains long selected values inside the trigger', () => {
    render(
      <Select label="Dataset" value="dataset-long" onValueChange={vi.fn()}>
        <SelectOption value="dataset-long">
          A very long historical dataset name · BTC/USDT · 1h
        </SelectOption>
      </Select>,
    );

    const trigger = screen.getByRole('combobox', {
      name: 'Dataset',
    });

    expect(trigger).toHaveClass('min-w-0', 'overflow-hidden');

    expect(
      screen.getByText('A very long historical dataset name · BTC/USDT · 1h'),
    ).toBeInTheDocument();

    const selectedValue = trigger.querySelector('[data-slot="select-value"]');

    expect(selectedValue).toHaveClass('min-w-0', 'flex-1', 'truncate');
  });
});
