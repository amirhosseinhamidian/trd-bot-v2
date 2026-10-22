import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Badge, type BadgeVariant } from '@/components/ui/badge';

const variantClasses: Record<BadgeVariant, string[]> = {
  neutral: ['border-app-border', 'bg-app-surface-muted', 'text-app-muted'],
  info: ['border-app-info-border', 'bg-app-info-soft', 'text-app-info'],
  success: ['border-app-success-border', 'bg-app-success-soft', 'text-app-success'],
  warning: ['border-app-warning-border', 'bg-app-warning-soft', 'text-app-warning'],
  danger: ['border-app-danger-border', 'bg-app-danger-soft', 'text-app-danger'],
};

describe('Badge', () => {
  it.each(Object.entries(variantClasses) as [BadgeVariant, string[]][])(
    'uses semantic tokens for the %s variant',
    (variant, classes) => {
      render(<Badge variant={variant}>{variant}</Badge>);

      expect(screen.getByText(variant)).toHaveClass(...classes);
    },
  );
});
