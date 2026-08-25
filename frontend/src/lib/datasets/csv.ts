import type { DatasetImportCandle, DatasetTimeframe } from '@/lib/api/types';

export type DatasetCsvErrorCode =
  | 'malformed_csv'
  | 'empty_file'
  | 'missing_header'
  | 'duplicate_header'
  | 'unknown_header'
  | 'empty_dataset'
  | 'invalid_column_count'
  | 'empty_value'
  | 'invalid_timestamp'
  | 'invalid_number'
  | 'invalid_ohlc'
  | 'open_candle'
  | 'duplicate_timestamp'
  | 'out_of_order'
  | 'missing_candle'
  | 'unexpected_interval';

export class DatasetCsvError extends Error {
  readonly code: DatasetCsvErrorCode;
  readonly row?: number;

  constructor(code: DatasetCsvErrorCode, message: string, row?: number) {
    super(message);

    this.name = 'DatasetCsvError';
    this.code = code;
    this.row = row;
  }
}

const REQUIRED_HEADERS = [
  'open_time',
  'close_time',
  'open_price',
  'high_price',
  'low_price',
  'close_price',
  'volume',
] as const;

const OPTIONAL_HEADERS = ['is_closed'] as const;

const ALLOWED_HEADERS = new Set<string>([...REQUIRED_HEADERS, ...OPTIONAL_HEADERS]);

const TIMEFRAME_INTERVAL_MS: Record<DatasetTimeframe, number> = {
  '15m': 15 * 60 * 1000,
  '1h': 60 * 60 * 1000,
  '4h': 4 * 60 * 60 * 1000,
  '1d': 24 * 60 * 60 * 1000,
};

const TIMEZONE_SUFFIX_PATTERN = /(?:Z|[+-]\d{2}:\d{2})$/iu;

const DECIMAL_PATTERN = /^(?:0|[1-9]\d*)(?:\.\d+)?(?:e[+-]?\d+)?$/iu;

function parseCsvRows(csvText: string): string[][] {
  const normalizedText = csvText.replace(/^\uFEFF/u, '').replace(/\r\n?/gu, '\n');

  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let insideQuotes = false;

  for (let index = 0; index < normalizedText.length; index += 1) {
    const character = normalizedText[index];

    if (insideQuotes) {
      if (character === '"') {
        if (normalizedText[index + 1] === '"') {
          field += '"';
          index += 1;
        } else {
          insideQuotes = false;
        }
      } else {
        field += character;
      }

      continue;
    }

    if (character === '"') {
      if (field.length > 0) {
        throw new DatasetCsvError('malformed_csv', 'A quoted field must start with a quote.');
      }

      insideQuotes = true;
      continue;
    }

    if (character === ',') {
      row.push(field);
      field = '';
      continue;
    }

    if (character === '\n') {
      row.push(field);
      rows.push(row);

      row = [];
      field = '';
      continue;
    }

    field += character;
  }

  if (insideQuotes) {
    throw new DatasetCsvError('malformed_csv', 'The CSV contains an unclosed quoted field.');
  }

  row.push(field);
  rows.push(row);

  return rows.filter((currentRow) =>
    currentRow.some((currentField) => currentField.trim().length > 0),
  );
}

function buildHeaderIndexes(rawHeaders: string[]): Map<string, number> {
  const headers = rawHeaders.map((header) => header.trim().toLowerCase());

  const indexes = new Map<string, number>();

  for (let index = 0; index < headers.length; index += 1) {
    const header = headers[index];

    if (!header) {
      throw new DatasetCsvError('missing_header', 'The CSV contains an empty header.');
    }

    if (indexes.has(header)) {
      throw new DatasetCsvError('duplicate_header', `The CSV header "${header}" is duplicated.`);
    }

    if (!ALLOWED_HEADERS.has(header)) {
      throw new DatasetCsvError('unknown_header', `The CSV header "${header}" is not supported.`);
    }

    indexes.set(header, index);
  }

  for (const requiredHeader of REQUIRED_HEADERS) {
    if (!indexes.has(requiredHeader)) {
      throw new DatasetCsvError(
        'missing_header',
        `The required CSV header "${requiredHeader}" is missing.`,
      );
    }
  }

  return indexes;
}

function getCell(row: string[], headerIndexes: Map<string, number>, header: string): string {
  const index = headerIndexes.get(header);

  if (index === undefined) {
    return '';
  }

  return row[index]?.trim() ?? '';
}

function getRequiredCell(
  row: string[],
  headerIndexes: Map<string, number>,
  header: string,
  rowNumber: number,
): string {
  const value = getCell(row, headerIndexes, header);

  if (!value) {
    throw new DatasetCsvError('empty_value', `The "${header}" value cannot be empty.`, rowNumber);
  }

  return value;
}

function parseTimestamp(value: string, fieldName: string, rowNumber: number): number {
  if (!TIMEZONE_SUFFIX_PATTERN.test(value)) {
    throw new DatasetCsvError(
      'invalid_timestamp',
      `The "${fieldName}" timestamp must include a timezone.`,
      rowNumber,
    );
  }

  const timestamp = Date.parse(value);

  if (Number.isNaN(timestamp)) {
    throw new DatasetCsvError(
      'invalid_timestamp',
      `The "${fieldName}" value is not a valid timestamp.`,
      rowNumber,
    );
  }

  return timestamp;
}

function parseDecimal(
  value: string,
  fieldName: string,
  rowNumber: number,
  allowZero: boolean,
): number {
  if (!DECIMAL_PATTERN.test(value)) {
    throw new DatasetCsvError(
      'invalid_number',
      `The "${fieldName}" value must be a valid decimal number.`,
      rowNumber,
    );
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue) || (allowZero ? numericValue < 0 : numericValue <= 0)) {
    throw new DatasetCsvError(
      'invalid_number',
      allowZero
        ? `The "${fieldName}" value cannot be negative.`
        : `The "${fieldName}" value must be greater than zero.`,
      rowNumber,
    );
  }

  return numericValue;
}

function parseClosedState(value: string, rowNumber: number): boolean {
  if (!value) {
    return true;
  }

  const normalizedValue = value.toLowerCase();

  if (normalizedValue === 'true') {
    return true;
  }

  if (normalizedValue === 'false') {
    return false;
  }

  throw new DatasetCsvError(
    'open_candle',
    'The "is_closed" value must be true or false.',
    rowNumber,
  );
}

type ParsedCandle = {
  candle: DatasetImportCandle;
  openTimestamp: number;
};

function parseCandleRow(
  row: string[],
  headerIndexes: Map<string, number>,
  rowNumber: number,
): ParsedCandle {
  if (row.length !== headerIndexes.size) {
    throw new DatasetCsvError(
      'invalid_column_count',
      `CSV row ${rowNumber} has an unexpected number of columns.`,
      rowNumber,
    );
  }

  const openTime = getRequiredCell(row, headerIndexes, 'open_time', rowNumber);

  const closeTime = getRequiredCell(row, headerIndexes, 'close_time', rowNumber);

  const openTimestamp = parseTimestamp(openTime, 'open_time', rowNumber);

  const closeTimestamp = parseTimestamp(closeTime, 'close_time', rowNumber);

  if (closeTimestamp <= openTimestamp) {
    throw new DatasetCsvError(
      'invalid_timestamp',
      'The close time must be after the open time.',
      rowNumber,
    );
  }

  const openPriceText = getRequiredCell(row, headerIndexes, 'open_price', rowNumber);

  const highPriceText = getRequiredCell(row, headerIndexes, 'high_price', rowNumber);

  const lowPriceText = getRequiredCell(row, headerIndexes, 'low_price', rowNumber);

  const closePriceText = getRequiredCell(row, headerIndexes, 'close_price', rowNumber);

  const volumeText = getRequiredCell(row, headerIndexes, 'volume', rowNumber);

  const openPrice = parseDecimal(openPriceText, 'open_price', rowNumber, false);

  const highPrice = parseDecimal(highPriceText, 'high_price', rowNumber, false);

  const lowPrice = parseDecimal(lowPriceText, 'low_price', rowNumber, false);

  const closePrice = parseDecimal(closePriceText, 'close_price', rowNumber, false);

  parseDecimal(volumeText, 'volume', rowNumber, true);

  if (
    highPrice < lowPrice ||
    highPrice < openPrice ||
    highPrice < closePrice ||
    lowPrice > openPrice ||
    lowPrice > closePrice
  ) {
    throw new DatasetCsvError('invalid_ohlc', 'The OHLC price relationship is invalid.', rowNumber);
  }

  const isClosed = parseClosedState(getCell(row, headerIndexes, 'is_closed'), rowNumber);

  if (!isClosed) {
    throw new DatasetCsvError(
      'open_candle',
      'Only closed historical candles can be imported.',
      rowNumber,
    );
  }

  return {
    openTimestamp,
    candle: {
      open_time: openTime,
      close_time: closeTime,
      open_price: openPriceText,
      high_price: highPriceText,
      low_price: lowPriceText,
      close_price: closePriceText,
      volume: volumeText,
      is_closed: true,
    },
  };
}

function validateChronology(parsedCandles: ParsedCandle[], timeframe: DatasetTimeframe): void {
  const expectedInterval = TIMEFRAME_INTERVAL_MS[timeframe];

  for (let index = 1; index < parsedCandles.length; index += 1) {
    const previous = parsedCandles[index - 1];
    const current = parsedCandles[index];

    const actualInterval = current.openTimestamp - previous.openTimestamp;

    const rowNumber = index + 2;

    if (actualInterval === 0) {
      throw new DatasetCsvError(
        'duplicate_timestamp',
        'The CSV contains a duplicate candle timestamp.',
        rowNumber,
      );
    }

    if (actualInterval < 0) {
      throw new DatasetCsvError(
        'out_of_order',
        'Candles must be sorted chronologically.',
        rowNumber,
      );
    }

    if (actualInterval > expectedInterval) {
      throw new DatasetCsvError(
        'missing_candle',
        'One or more candles are missing from the time series.',
        rowNumber,
      );
    }

    if (actualInterval < expectedInterval) {
      throw new DatasetCsvError(
        'unexpected_interval',
        'The candle interval does not match the selected timeframe.',
        rowNumber,
      );
    }
  }
}

export function parseDatasetCsv(
  csvText: string,
  timeframe: DatasetTimeframe,
): DatasetImportCandle[] {
  const rows = parseCsvRows(csvText);

  if (rows.length === 0) {
    throw new DatasetCsvError('empty_file', 'The selected CSV file is empty.');
  }

  const headerRow = rows[0];

  if (!headerRow) {
    throw new DatasetCsvError('missing_header', 'The CSV header row is missing.');
  }

  const headerIndexes = buildHeaderIndexes(headerRow);

  const dataRows = rows.slice(1);

  if (dataRows.length === 0) {
    throw new DatasetCsvError('empty_dataset', 'The CSV does not contain any candle rows.');
  }

  const parsedCandles = dataRows.map((row, index) => parseCandleRow(row, headerIndexes, index + 2));

  validateChronology(parsedCandles, timeframe);

  return parsedCandles.map(({ candle }) => candle);
}
