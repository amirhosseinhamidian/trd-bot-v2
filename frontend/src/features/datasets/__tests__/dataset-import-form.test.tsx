import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DatasetImportForm from '@/features/datasets/dataset-import-form';
import type {
  DatasetColumnMapping,
  DatasetFileImportPreview,
  DatasetFileInspection,
} from '@/features/datasets/api/types';
import type { BackgroundJobSummary } from '@/features/jobs/api/types';

const mocks = vi.hoisted(() => ({
  importDatasetFile: vi.fn(),
  inspectDatasetFile: vi.fn(),
  previewDatasetFile: vi.fn(),
}));

vi.mock('@/features/datasets/api/client', () => mocks);

const mapping = {
  open_time: 'timestamp',
  close_time: 'end',
  open_price: 'open',
  high_price: 'high',
  low_price: 'low',
  close_price: 'close',
  volume: 'vol',
  is_closed: 'closed',
} satisfies DatasetColumnMapping;

const inspection: DatasetFileInspection = {
  file_name: 'btc.csv',
  file_format: 'csv',
  file_size_bytes: 120,
  file_checksum: 'b'.repeat(64),
  row_count: 2,
  columns: ['timestamp', 'end', 'open', 'high', 'low', 'close', 'vol', 'closed'],
  suggested_mapping: mapping,
  missing_required_fields: [],
  can_preview: true,
};

const preview: DatasetFileImportPreview = {
  inspection,
  column_mapping: mapping,
  candle_count: 2,
  first_open_time: '2026-08-20T10:00:00.000Z',
  last_close_time: '2026-08-20T12:00:00.000Z',
  preview_checksum: 'a'.repeat(64),
  quality_report: {
    candles_checked: 2,
    issues: [],
    coverage: null,
    score: {
      score_version: 'quality-score-v1',
      score_percent: 100,
      coverage_percent: 100,
      integrity_percent: 100,
    },
    acceptance: {
      policy_version: 'strict-quality-v1',
      accepted: true,
      minimum_score_percent: 100,
      blocking_issue_codes: [],
    },
  },
  ready_to_import: true,
};

const queuedJob: BackgroundJobSummary = {
  job_id: 'job-1234567890abcdef1234',
  kind: 'dataset_file_import',
  status: 'queued',
  progress_percent: 0,
  attempt_count: 0,
  max_attempts: 3,
  run_after: '2026-10-10T08:00:00.000Z',
  lease_expires_at: null,
  cancel_requested: false,
  result_reference: null,
  error_code: null,
  error_message: null,
  created_at: '2026-08-25T10:00:00.000Z',
  updated_at: '2026-08-25T10:00:00.000Z',
  started_at: null,
  finished_at: null,
};

async function fillAndInspect(user: ReturnType<typeof userEvent.setup>): Promise<File> {
  await user.type(screen.getByLabelText('Dataset name'), 'BTC historical');
  await user.type(screen.getByLabelText('Data source'), 'manual-import');
  await user.type(screen.getByLabelText('Base asset'), 'btc');
  await user.type(screen.getByLabelText('Quote asset'), 'usdt');

  const file = new File(['csv contents'], 'btc.csv', { type: 'text/csv' });
  await user.upload(screen.getByLabelText('Dataset file'), file);
  await waitFor(() => expect(mocks.inspectDatasetFile).toHaveBeenCalledWith(file));
  return file;
}

describe('DatasetImportForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('validates required fields before previewing', async () => {
    const user = userEvent.setup();
    render(<DatasetImportForm locale="en" />);

    await user.click(screen.getByRole('button', { name: 'Build preview' }));

    expect(screen.getByText('Select a dataset file first.')).toBeInTheDocument();
    expect(mocks.previewDatasetFile).not.toHaveBeenCalled();
  });

  it('inspects, previews, and commits the exact uploaded file', async () => {
    const user = userEvent.setup();
    const onQueued = vi.fn();
    mocks.inspectDatasetFile.mockResolvedValue(inspection);
    mocks.previewDatasetFile.mockResolvedValue(preview);
    mocks.importDatasetFile.mockResolvedValue(queuedJob);

    render(<DatasetImportForm locale="en" onQueued={onQueued} />);
    const file = await fillAndInspect(user);

    expect(await screen.findByText('Column mapping')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Build preview' }));

    const expectedRequest = {
      name: 'BTC historical',
      source: 'manual-import',
      pair: {
        base_asset: 'BTC',
        quote_asset: 'USDT',
        market_type: 'spot',
      },
      timeframe: '1h',
      column_mapping: mapping,
    };
    await waitFor(() => {
      expect(mocks.previewDatasetFile).toHaveBeenCalledWith(file, expectedRequest);
    });

    expect(await screen.findByText('Ready to import')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Queue approved dataset' }));

    await waitFor(() => {
      expect(mocks.importDatasetFile).toHaveBeenCalledWith(file, {
        ...expectedRequest,
        preview_checksum: preview.preview_checksum,
      });
    });
    expect(onQueued).toHaveBeenCalledWith(queuedJob);
    expect(screen.getByText('Dataset import queued')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Track in monitoring' })).toHaveAttribute(
      'href',
      '/en/monitoring',
    );
  });

  it('does not allow a quality-rejected preview to be committed', async () => {
    const user = userEvent.setup();
    mocks.inspectDatasetFile.mockResolvedValue(inspection);
    mocks.previewDatasetFile.mockResolvedValue({
      ...preview,
      ready_to_import: false,
      quality_report: {
        ...preview.quality_report,
        issues: [
          {
            code: 'missing_candle',
            message: 'A candle is missing.',
            timestamp: preview.first_open_time,
          },
        ],
        acceptance: {
          ...preview.quality_report.acceptance!,
          accepted: false,
          blocking_issue_codes: ['missing_candle'],
        },
      },
    });

    render(<DatasetImportForm locale="en" />);
    await fillAndInspect(user);
    await user.click(screen.getByRole('button', { name: 'Build preview' }));

    const importButton = await screen.findByRole('button', {
      name: 'Queue approved dataset',
    });
    expect(importButton).toBeDisabled();
    expect(
      screen.getByText('Dataset quality was rejected. Resolve the preview issues first.'),
    ).toBeInTheDocument();
    expect(mocks.importDatasetFile).not.toHaveBeenCalled();
  });
});
