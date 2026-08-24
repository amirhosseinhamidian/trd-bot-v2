export type HistoricalChartPoint = {
  timestamp: string;
  value: number;
};

export type HistoricalChartSeries = {
  color: string;
  label: string;
  points: HistoricalChartPoint[];
};

type HistoricalLineChartProps = {
  ariaLabel: string;
  clampMinimumToZero?: boolean;
  emptyLabel: string;
  formatDate: (value: string) => string;
  formatValue: (value: number) => string;
  minimumDomainSpan?: number;
  series: HistoricalChartSeries[];
};

type NormalizedPoint = HistoricalChartPoint & {
  milliseconds: number;
};

type NormalizedSeries = Omit<HistoricalChartSeries, 'points'> & {
  points: NormalizedPoint[];
};

const WIDTH = 800;
const HEIGHT = 300;
const PADDING_LEFT = 70;
const PADDING_RIGHT = 24;
const PADDING_TOP = 24;
const PADDING_BOTTOM = 48;
const GRID_LINE_COUNT = 4;

function normalizeSeries(series: HistoricalChartSeries[]): NormalizedSeries[] {
  return series.map((item) => ({
    ...item,
    points: item.points
      .map((point) => ({
        ...point,
        milliseconds: new Date(point.timestamp).getTime(),
      }))
      .filter((point) => Number.isFinite(point.value) && Number.isFinite(point.milliseconds))
      .sort((first, second) => first.milliseconds - second.milliseconds),
  }));
}

export function HistoricalLineChart({
  ariaLabel,
  clampMinimumToZero = false,
  emptyLabel,
  formatDate,
  formatValue,
  minimumDomainSpan = 1,
  series,
}: HistoricalLineChartProps) {
  const normalizedSeries = normalizeSeries(series);

  const allPoints = normalizedSeries.flatMap((item) => item.points);

  if (allPoints.length === 0) {
    return (
      <div className="flex min-h-64 items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 p-6 text-center">
        <p className="text-sm text-slate-500">{emptyLabel}</p>
      </div>
    );
  }

  const minimumTime = Math.min(...allPoints.map((point) => point.milliseconds));
  const maximumTime = Math.max(...allPoints.map((point) => point.milliseconds));

  const values = allPoints.map((point) => point.value);
  const minimumValue = Math.min(...values);
  const maximumValue = Math.max(...values);
  const rawValueSpan = maximumValue - minimumValue;

  let chartMinimumValue: number;
  let chartMaximumValue: number;

  if (rawValueSpan === 0) {
    if (maximumValue === 0 && clampMinimumToZero) {
      chartMinimumValue = 0;
      chartMaximumValue = minimumDomainSpan;
    } else {
      chartMinimumValue = minimumValue - minimumDomainSpan / 2;
      chartMaximumValue = maximumValue + minimumDomainSpan / 2;
    }
  } else {
    const padding = rawValueSpan * 0.08;

    chartMinimumValue = minimumValue - padding;
    chartMaximumValue = maximumValue + padding;

    if (clampMinimumToZero) {
      chartMinimumValue = Math.max(0, chartMinimumValue);
    }
  }

  const chartWidth = WIDTH - PADDING_LEFT - PADDING_RIGHT;
  const chartHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const timeSpan = maximumTime - minimumTime;
  const valueSpan = chartMaximumValue - chartMinimumValue;

  function scaleX(milliseconds: number): number {
    if (timeSpan === 0) {
      return PADDING_LEFT + chartWidth / 2;
    }

    return PADDING_LEFT + ((milliseconds - minimumTime) / timeSpan) * chartWidth;
  }

  function scaleY(value: number): number {
    return PADDING_TOP + (1 - (value - chartMinimumValue) / valueSpan) * chartHeight;
  }

  function createPath(points: NormalizedPoint[]): string {
    return points
      .map((point, index) => {
        const command = index === 0 ? 'M' : 'L';

        return `${command} ${scaleX(point.milliseconds).toFixed(
          2,
        )} ${scaleY(point.value).toFixed(2)}`;
      })
      .join(' ');
  }

  const gridLines = Array.from(
    {
      length: GRID_LINE_COUNT + 1,
    },
    (_, index) => {
      const fraction = index / GRID_LINE_COUNT;
      const value = chartMaximumValue - fraction * valueSpan;

      return {
        value,
        y: PADDING_TOP + fraction * chartHeight,
      };
    },
  );

  const firstTimestamp = new Date(minimumTime).toISOString();
  const lastTimestamp = new Date(maximumTime).toISOString();

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-4">
        {normalizedSeries.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-xs text-slate-400">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{
                backgroundColor: item.color,
              }}
            />

            <span>{item.label}</span>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/50 p-3">
        <svg
          role="img"
          aria-label={ariaLabel}
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="h-auto w-full"
        >
          {gridLines.map((line) => (
            <g key={line.y}>
              <line
                x1={PADDING_LEFT}
                x2={WIDTH - PADDING_RIGHT}
                y1={line.y}
                y2={line.y}
                stroke="#1e293b"
                strokeWidth="1"
              />

              <text
                x={PADDING_LEFT - 10}
                y={line.y + 4}
                fill="#64748b"
                fontSize="11"
                textAnchor="end"
              >
                {formatValue(line.value)}
              </text>
            </g>
          ))}

          <line
            x1={PADDING_LEFT}
            x2={PADDING_LEFT}
            y1={PADDING_TOP}
            y2={HEIGHT - PADDING_BOTTOM}
            stroke="#334155"
            strokeWidth="1"
          />

          <line
            x1={PADDING_LEFT}
            x2={WIDTH - PADDING_RIGHT}
            y1={HEIGHT - PADDING_BOTTOM}
            y2={HEIGHT - PADDING_BOTTOM}
            stroke="#334155"
            strokeWidth="1"
          />

          {normalizedSeries.map((item) => {
            const path = createPath(item.points);

            return (
              <g key={item.label}>
                {item.points.length > 1 ? (
                  <path
                    d={path}
                    fill="none"
                    stroke={item.color}
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    vectorEffect="non-scaling-stroke"
                  />
                ) : null}

                {item.points.map((point) => (
                  <circle
                    key={`${item.label}-${point.timestamp}`}
                    cx={scaleX(point.milliseconds)}
                    cy={scaleY(point.value)}
                    r="4"
                    fill={item.color}
                    stroke="#020617"
                    strokeWidth="2"
                    vectorEffect="non-scaling-stroke"
                  >
                    <title>
                      {item.label}: {formatValue(point.value)} — {formatDate(point.timestamp)}
                    </title>
                  </circle>
                ))}
              </g>
            );
          })}

          <text x={PADDING_LEFT} y={HEIGHT - 15} fill="#64748b" fontSize="11" textAnchor="start">
            {formatDate(firstTimestamp)}
          </text>

          <text
            x={WIDTH - PADDING_RIGHT}
            y={HEIGHT - 15}
            fill="#64748b"
            fontSize="11"
            textAnchor="end"
          >
            {formatDate(lastTimestamp)}
          </text>
        </svg>
      </div>
    </div>
  );
}
