import { describe, expect, it } from 'vitest';

import { DatasetCsvError, type DatasetCsvErrorCode, parseDatasetCsv } from '@/lib/datasets/csv';
import type { DatasetTimeframe } from '@/lib/api/types';

const CSV_HEADER =
  'open_time,close_time,open_price,high_price,low_price,close_price,volume,is_closed';

const FIRST_CANDLE = '2026-08-20T10:00:00.000Z,2026-08-20T11:00:00.000Z,100,102,99,101,1500,true';

const SECOND_CANDLE = '2026-08-20T11:00:00.000Z,2026-08-20T12:00:00.000Z,101,103,100,102,1600,true';

function expectCsvError(
  csv: string,
  expectedCode: DatasetCsvErrorCode,
  timeframe: DatasetTimeframe = '1h',
): void {
  try {
    parseDatasetCsv(csv, timeframe);
  } catch (error) {
    expect(error).toBeInstanceOf(DatasetCsvError);

    expect((error as DatasetCsvError).code).toBe(expectedCode);

    return;
  }

  throw new Error(`Expected DatasetCsvError with code "${expectedCode}".`);
}

describe('parseDatasetCsv', () => {
  it('parses valid historical candles', () => {
    const csv = [`\uFEFF${CSV_HEADER}`, FIRST_CANDLE, SECOND_CANDLE].join('\r\n');

    const candles = parseDatasetCsv(csv, '1h');

    expect(candles).toHaveLength(2);

    expect(candles[0]).toEqual({
      open_time: '2026-08-20T10:00:00.000Z',
      close_time: '2026-08-20T11:00:00.000Z',
      open_price: '100',
      high_price: '102',
      low_price: '99',
      close_price: '101',
      volume: '1500',
      is_closed: true,
    });
  });

  it('defaults is_closed to true when the column is omitted', () => {
    const csv = [
      [
        'open_time',
        'close_time',
        'open_price',
        'high_price',
        'low_price',
        'close_price',
        'volume',
      ].join(','),
      [
        '2026-08-20T10:00:00.000Z',
        '2026-08-20T11:00:00.000Z',
        '100',
        '102',
        '99',
        '101',
        '1500',
      ].join(','),
    ].join('\n');

    const candles = parseDatasetCsv(csv, '1h');

    expect(candles[0]?.is_closed).toBe(true);
  });

  it('rejects a missing required header', () => {
    const csv = [
      'open_time,close_time,open_price,high_price,low_price,close_price,is_closed',
      '2026-08-20T10:00:00.000Z,2026-08-20T11:00:00.000Z,100,102,99,101,true',
    ].join('\n');

    expectCsvError(csv, 'missing_header');
  });

  it('rejects timestamps without timezone information', () => {
    const csv = [
      CSV_HEADER,
      '2026-08-20T10:00:00,2026-08-20T11:00:00,100,102,99,101,1500,true',
    ].join('\n');

    expectCsvError(csv, 'invalid_timestamp');
  });

  it('rejects invalid OHLC relationships', () => {
    const csv = [
      CSV_HEADER,
      '2026-08-20T10:00:00.000Z,2026-08-20T11:00:00.000Z,100,100,99,101,1500,true',
    ].join('\n');

    expectCsvError(csv, 'invalid_ohlc');
  });

  it('rejects unclosed candles', () => {
    const csv = [
      CSV_HEADER,
      '2026-08-20T10:00:00.000Z,2026-08-20T11:00:00.000Z,100,102,99,101,1500,false',
    ].join('\n');

    expectCsvError(csv, 'open_candle');
  });

  it('rejects missing candles', () => {
    const delayedCandle =
      '2026-08-20T12:00:00.000Z,2026-08-20T13:00:00.000Z,101,103,100,102,1600,true';

    const csv = [CSV_HEADER, FIRST_CANDLE, delayedCandle].join('\n');

    expectCsvError(csv, 'missing_candle');
  });

  it('rejects intervals that do not match the timeframe', () => {
    const earlyCandle =
      '2026-08-20T10:30:00.000Z,2026-08-20T11:30:00.000Z,101,103,100,102,1600,true';

    const csv = [CSV_HEADER, FIRST_CANDLE, earlyCandle].join('\n');

    expectCsvError(csv, 'unexpected_interval');
  });

  it('rejects duplicate timestamps', () => {
    const duplicateCandle =
      '2026-08-20T10:00:00.000Z,2026-08-20T11:00:00.000Z,101,103,100,102,1600,true';

    const csv = [CSV_HEADER, FIRST_CANDLE, duplicateCandle].join('\n');

    expectCsvError(csv, 'duplicate_timestamp');
  });
});
