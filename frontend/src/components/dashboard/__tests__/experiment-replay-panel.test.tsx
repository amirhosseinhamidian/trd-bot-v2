import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ExperimentReplayPanel } from '@/components/dashboard/experiment-replay-panel';
import type { ExperimentReplayVerification } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  verifyExperimentReplay: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  verifyExperimentReplay: mocks.verifyExperimentReplay,
}));

const verification: ExperimentReplayVerification = {
  experiment_id: 'experiment-1234567890abcdef',
  checked_at: '2026-09-26T12:00:00Z',
  status: 'verified',
  code: 'verified',
  dataset_id: 'dataset-1234567890abcdef',
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  recorded_strategy_fingerprint: `sha256:${'a'.repeat(64)}`,
  current_strategy_fingerprint: `sha256:${'a'.repeat(64)}`,
  recorded_result_checksum: 'b'.repeat(64),
  replayed_result_checksum: 'b'.repeat(64),
  mismatch_fields: [],
};

describe('ExperimentReplayPanel', () => {
  beforeEach(() => {
    mocks.verifyExperimentReplay.mockReset();
  });

  it('runs replay verification only on request and renders immutable evidence', async () => {
    const user = userEvent.setup();
    mocks.verifyExperimentReplay.mockResolvedValueOnce(verification);

    render(<ExperimentReplayPanel experimentId={verification.experiment_id} locale="en" />);

    expect(screen.getByText(/never overwrites the historical record/u)).toBeInTheDocument();
    expect(mocks.verifyExperimentReplay).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Verify reproducibility' }));

    expect(mocks.verifyExperimentReplay).toHaveBeenCalledWith(verification.experiment_id);
    expect(await screen.findByText('Verification outcome: Verified')).toBeInTheDocument();
    expect(screen.getAllByText('b'.repeat(64))).toHaveLength(2);
    expect(screen.getByText(/exactly matches the stored result/u)).toBeInTheDocument();
  });

  it('shows a retry-safe error without retaining stale evidence', async () => {
    const user = userEvent.setup();
    mocks.verifyExperimentReplay.mockRejectedValueOnce(new Error('offline'));

    render(<ExperimentReplayPanel experimentId={verification.experiment_id} locale="en" />);
    await user.click(screen.getByRole('button', { name: 'Verify reproducibility' }));

    expect(await screen.findByText(/Replay verification failed/u)).toBeInTheDocument();
    expect(screen.queryByText('Verification outcome: Verified')).toBeNull();
  });
});
