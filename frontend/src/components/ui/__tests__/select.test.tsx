import { fireEvent, render, screen } from '@testing-library/react';
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

  it('uses the app-scoped animation hook for its popup content', async () => {
    render(
      <Select label="Dataset" defaultValue="btc">
        <SelectOption value="btc">BTC/USDT</SelectOption>
      </Select>,
    );

    fireEvent.keyDown(screen.getByRole('combobox', { name: 'Dataset' }), {
      key: 'ArrowDown',
    });

    expect(await screen.findByRole('listbox')).toHaveClass('app-select-content');
    expect(screen.getByRole('option', { name: 'BTC/USDT' })).toHaveClass('min-h-11');
    expect(document.querySelector('.trd-select-content')).not.toBeInTheDocument();
  });

  it('exposes semantic focus and error states accessibly', () => {
    render(
      <Select label="Dataset" defaultValue="btc" error="Choose an available dataset">
        <SelectOption value="btc">BTC/USDT</SelectOption>
      </Select>,
    );

    const trigger = screen.getByRole('combobox', { name: 'Dataset' });
    const error = screen.getByRole('alert');

    expect(trigger).toHaveAttribute('aria-invalid', 'true');
    expect(trigger).toHaveAttribute('aria-describedby', error.id);
    expect(trigger).toHaveClass(
      'border-app-danger',
      'focus:border-app-danger',
      'focus:ring-app-danger-soft',
    );
    expect(error).toHaveClass('text-app-danger');
  });
});
