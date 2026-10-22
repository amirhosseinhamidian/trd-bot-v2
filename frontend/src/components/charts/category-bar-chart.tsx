export type CategoryChartPoint = {
  category: string;
  value: number;
};

export type CategoryChartSeries = {
  color: string;
  label: string;
  points: CategoryChartPoint[];
};

type CategoryBarChartProps = {
  ariaLabel: string;
  emptyLabel: string;
  formatValue: (value: number) => string;
  minimumDomainSpan?: number;
  series: CategoryChartSeries[];
};

const WIDTH = 800;
const HEIGHT = 320;
const PADDING_LEFT = 70;
const PADDING_RIGHT = 24;
const PADDING_TOP = 24;
const PADDING_BOTTOM = 58;
const GRID_LINE_COUNT = 4;
const MINIMUM_CATEGORY_WIDTH = 88;

export function CategoryBarChart({
  ariaLabel,
  emptyLabel,
  formatValue,
  minimumDomainSpan = 1,
  series,
}: CategoryBarChartProps) {
  const normalizedSeries = series.map((item) => ({
    ...item,
    points: item.points.filter((point) => Number.isFinite(point.value)),
  }));
  const categories = Array.from(
    new Set(normalizedSeries.flatMap((item) => item.points.map((point) => point.category))),
  );
  const allValues = normalizedSeries.flatMap((item) => item.points.map((point) => point.value));

  if (categories.length === 0 || allValues.length === 0) {
    return (
      <div className="flex min-h-64 items-center justify-center rounded-2xl border border-dashed border-app-border bg-app-surface-muted p-6 text-center">
        <p className="text-sm text-app-muted">{emptyLabel}</p>
      </div>
    );
  }

  const canvasWidth = Math.max(
    WIDTH,
    PADDING_LEFT + PADDING_RIGHT + categories.length * MINIMUM_CATEGORY_WIDTH,
  );

  let minimumValue = Math.min(0, ...allValues);
  let maximumValue = Math.max(0, ...allValues);
  if (minimumValue === maximumValue) {
    maximumValue = minimumValue + minimumDomainSpan;
  } else if (maximumValue - minimumValue < minimumDomainSpan) {
    const padding = (minimumDomainSpan - (maximumValue - minimumValue)) / 2;
    minimumValue -= padding;
    maximumValue += padding;
  }

  const chartWidth = canvasWidth - PADDING_LEFT - PADDING_RIGHT;
  const chartHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const valueSpan = maximumValue - minimumValue;
  const categoryWidth = chartWidth / categories.length;
  const seriesCount = Math.max(normalizedSeries.length, 1);
  const groupWidth = categoryWidth * 0.72;
  const barWidth = Math.max(2, groupWidth / seriesCount - 3);

  function scaleY(value: number): number {
    return PADDING_TOP + (1 - (value - minimumValue) / valueSpan) * chartHeight;
  }

  const zeroY = scaleY(0);
  const gridLines = Array.from({ length: GRID_LINE_COUNT + 1 }, (_, index) => {
    const fraction = index / GRID_LINE_COUNT;
    return {
      value: maximumValue - fraction * valueSpan,
      y: PADDING_TOP + fraction * chartHeight,
    };
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-4">
        {normalizedSeries.map((item) => (
          <div key={item.label} className="flex items-center gap-2 text-xs text-app-muted">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: item.color }} />
            <span>{item.label}</span>
          </div>
        ))}
      </div>

      <div
        role="region"
        aria-label={ariaLabel}
        tabIndex={0}
        className="w-full max-w-full min-w-0 touch-pan-x touch-pan-y [scrollbar-gutter:stable] overflow-x-auto overflow-y-hidden overscroll-x-contain rounded-2xl border border-app-border bg-app-surface-muted p-3 focus-visible:border-app-control-border focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none focus-visible:ring-inset"
      >
        <svg
          role="img"
          aria-label={ariaLabel}
          viewBox={`0 0 ${canvasWidth} ${HEIGHT}`}
          className="h-auto"
          style={{ minWidth: `${canvasWidth}px`, width: '100%' }}
        >
          {gridLines.map((line) => (
            <g key={line.y}>
              <line
                x1={PADDING_LEFT}
                x2={canvasWidth - PADDING_RIGHT}
                y1={line.y}
                y2={line.y}
                stroke="var(--app-border)"
                strokeWidth="1"
              />
              <text
                x={PADDING_LEFT - 10}
                y={line.y + 4}
                fill="var(--app-subtle)"
                fontSize="11"
                textAnchor="end"
              >
                {formatValue(line.value)}
              </text>
            </g>
          ))}

          <line
            x1={PADDING_LEFT}
            x2={canvasWidth - PADDING_RIGHT}
            y1={zeroY}
            y2={zeroY}
            stroke="var(--app-muted)"
            strokeWidth="1.5"
          />

          {categories.map((category, categoryIndex) => {
            const groupStart =
              PADDING_LEFT + categoryIndex * categoryWidth + (categoryWidth - groupWidth) / 2;

            return (
              <g key={category}>
                {normalizedSeries.map((item, seriesIndex) => {
                  const point = item.points.find((candidate) => candidate.category === category);
                  if (point === undefined) {
                    return null;
                  }

                  const valueY = scaleY(point.value);
                  const rawHeight = Math.abs(valueY - zeroY);
                  const height = Math.max(2, rawHeight);
                  const y = point.value >= 0 ? zeroY - height : zeroY;

                  return (
                    <rect
                      key={`${category}-${item.label}`}
                      x={groupStart + seriesIndex * (barWidth + 3)}
                      y={y}
                      width={barWidth}
                      height={height}
                      rx="2"
                      fill={item.color}
                    >
                      <title>
                        {item.label}: {formatValue(point.value)} — {category}
                      </title>
                    </rect>
                  );
                })}

                <text
                  x={PADDING_LEFT + (categoryIndex + 0.5) * categoryWidth}
                  y={HEIGHT - 22}
                  fill="var(--app-subtle)"
                  fontSize="11"
                  textAnchor="middle"
                >
                  {category}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
