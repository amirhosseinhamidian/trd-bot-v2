import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Select, SelectOption } from '@/components/ui/select';

describe('Select', () => {
  it('renders the controlled value in a browser-native control', () => {
    render(
      <Select label="Dataset" value="dataset-long" onValueChange={vi.fn()}>
        <SelectOption value="dataset-long">
          A very long historical dataset name · BTC/USDT · 1h
        </SelectOption>
      </Select>,
    );

    const select = screen.getByRole('combobox', {
      name: 'Dataset',
    });

    expect(select).toBeInstanceOf(HTMLSelectElement);
    expect(select).toHaveValue('dataset-long');
    expect(select).toHaveTextContent('A very long historical dataset name · BTC/USDT · 1h');
    expect(select).toHaveClass('min-w-0', 'appearance-none');
  });

  it('reports native changes through the existing onValueChange contract', () => {
    const onValueChange = vi.fn();

    render(
      <Select label="Dataset" defaultValue="btc" onValueChange={onValueChange}>
        <SelectOption value="btc">BTC/USDT</SelectOption>
        <SelectOption value="eth">ETH/USDT</SelectOption>
      </Select>,
    );

    fireEvent.change(screen.getByRole('combobox', { name: 'Dataset' }), {
      target: { value: 'eth' },
    });

    expect(onValueChange).toHaveBeenCalledWith('eth');
  });

  it('renders a disabled native placeholder for an empty value', () => {
    render(
      <Select label="Dataset" value="" placeholder="Choose a dataset" onValueChange={vi.fn()}>
        <SelectOption value="btc">BTC/USDT</SelectOption>
      </Select>,
    );

    const select = screen.getByRole('combobox', { name: 'Dataset' });
    const placeholder = screen.getByRole('option', { name: 'Choose a dataset' });

    expect(select).toHaveValue('');
    expect(placeholder).toBeDisabled();
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
