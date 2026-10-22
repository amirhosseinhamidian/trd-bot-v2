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
    expect(button).toHaveClass(
      'bg-app-accent',
      'text-app-background',
      'hover:bg-app-accent-hover',
      'focus-visible:ring-app-accent',
    );
  });

  it('uses semantic contrast states for secondary and danger actions', () => {
    const { rerender } = render(<Button variant="secondary">Cancel</Button>);

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveClass(
      'border-app-control-border',
      'hover:border-app-muted',
      'focus-visible:ring-app-accent',
    );

    rerender(<Button variant="danger">Delete</Button>);

    expect(screen.getByRole('button', { name: 'Delete' })).toHaveClass(
      'border-app-danger-border',
      'bg-app-danger-soft',
      'text-app-danger',
      'focus-visible:ring-app-danger',
    );
  });

  it('keeps every size at least touch-target height', () => {
    const { rerender } = render(<Button size="sm">Small action</Button>);

    expect(screen.getByRole('button', { name: 'Small action' })).toHaveClass('min-h-11');

    rerender(<Button size="md">Medium action</Button>);
    expect(screen.getByRole('button', { name: 'Medium action' })).toHaveClass('min-h-11');

    rerender(<Button size="icon">Icon action</Button>);
    expect(screen.getByRole('button', { name: 'Icon action' })).toHaveClass('h-11', 'w-11');
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
