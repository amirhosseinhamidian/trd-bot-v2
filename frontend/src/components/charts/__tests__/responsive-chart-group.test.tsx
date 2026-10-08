import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ResponsiveChartGroup } from '@/components/charts/responsive-chart-group';

describe('ResponsiveChartGroup', () => {
  it('uses a touch-friendly mobile selector while keeping desktop panels stacked', async () => {
    const user = userEvent.setup();

    render(
      <ResponsiveChartGroup
        selectorLabel="Select chart metric"
        items={[
          {
            id: 'equity',
            label: 'Equity',
            summary: <p>Latest equity: 1,100</p>,
            chart: <div>Equity chart</div>,
          },
          {
            id: 'drawdown',
            label: 'Drawdown',
            summary: <p>Maximum drawdown: 5%</p>,
            chart: <div>Drawdown chart</div>,
          },
        ]}
      />,
    );

    const equityButton = screen.getByRole('button', { name: 'Equity' });
    const drawdownButton = screen.getByRole('button', { name: 'Drawdown' });
    const equityPanel = screen.getByTestId('responsive-chart-panel-equity');
    const drawdownPanel = screen.getByTestId('responsive-chart-panel-drawdown');

    expect(screen.getByRole('group', { name: 'Select chart metric' }).parentElement).toHaveClass(
      'md:hidden',
    );
    expect(equityButton).toHaveAttribute('aria-pressed', 'true');
    expect(drawdownButton).toHaveAttribute('aria-pressed', 'false');
    expect(equityButton).toHaveClass('min-h-11', 'w-full');
    expect(equityPanel).toHaveClass('block');
    expect(drawdownPanel).toHaveClass('hidden', 'md:block', 'md:border-t', 'md:pt-8');

    await user.click(drawdownButton);

    expect(equityButton).toHaveAttribute('aria-pressed', 'false');
    expect(drawdownButton).toHaveAttribute('aria-pressed', 'true');
    expect(equityPanel).toHaveClass('hidden', 'md:block');
    expect(drawdownPanel).toHaveClass('block');
    expect(screen.getByText('Maximum drawdown: 5%')).toBeInTheDocument();
  });
});
