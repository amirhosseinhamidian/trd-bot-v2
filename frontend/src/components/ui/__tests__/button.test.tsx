import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Button } from '@/components/ui/button';

describe('Button', () => {
  it('calls the click handler', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(<Button onClick={onClick}>Run test</Button>);

    await user.click(
      screen.getByRole('button', {
        name: 'Run test',
      }),
    );

    const button = screen.getByRole('button', {
      name: 'Run test',
    });

    expect(onClick).toHaveBeenCalledOnce();
    expect(button).toHaveClass('bg-app-accent', 'text-app-background');
  });

  it('is disabled while loading', () => {
    render(
      <Button isLoading loadingText="Loading">
        Run test
      </Button>,
    );

    const button = screen.getByRole('button', {
      name: 'Loading',
    });

    expect(button).toBeDisabled();
    expect(button).toHaveTextContent('Loading');
  });

  it('does not call the handler when disabled', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(
      <Button disabled onClick={onClick}>
        Disabled action
      </Button>,
    );

    await user.click(
      screen.getByRole('button', {
        name: 'Disabled action',
      }),
    );

    expect(onClick).not.toHaveBeenCalled();
  });
});
