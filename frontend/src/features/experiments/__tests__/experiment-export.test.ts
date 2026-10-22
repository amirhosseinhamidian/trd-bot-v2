import { afterEach, describe, expect, it, vi } from 'vitest';

import { getExperimentReportCsv } from '@/features/experiments/api/client';
import { API_BASE_URL } from '@/lib/api/core/transport';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('minimum experiment export contract', () => {
  it('downloads the versioned CSV report through the no-store blob boundary', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        'section,metric,value\nmetadata,export_schema_version,experiment-report-csv-v1\n',
        {
          status: 200,
          headers: {
            'Content-Type': 'text/csv; charset=utf-8',
          },
        },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await getExperimentReportCsv('experiment/id', 'baseline/v1');

    await expect(result.text()).resolves.toContain('experiment-report-csv-v1');
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/experiments/experiment%2Fid/report/presets/baseline%2Fv1/export.csv`,
      {
        method: 'GET',
        headers: { Accept: 'text/csv' },
        cache: 'no-store',
      },
    );
  });
});
