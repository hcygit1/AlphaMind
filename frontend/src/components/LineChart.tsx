// 轻量 SVG 折线图（零依赖）：多序列 + 参考线 + 坐标刻度，供 Factor/Strategy Lab 复用。

export type ChartSeries = {
  name: string;
  color: string;
  values: number[];
};

const VIEW_W = 820;
const VIEW_H = 300;
const PAD_L = 56;
const PAD_R = 16;
const PAD_T = 14;
const PAD_B = 30;

function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) {
    return [min];
  }
  const step = (max - min) / (count - 1);
  return Array.from({ length: count }, (_, i) => min + i * step);
}

export function LineChart({
  series,
  labels,
  refLine,
  yFormat = (v) => v.toFixed(2),
  height
}: {
  series: ChartSeries[];
  labels: string[];
  /** 参考线（如 IC 的 0、净值的 1），会强制纳入值域 */
  refLine?: number;
  yFormat?: (v: number) => string;
  height?: number;
}) {
  const valid = series.flatMap((s) => s.values).filter((v) => Number.isFinite(v));
  if (!valid.length || !labels.length) {
    return <p className="chart-empty">暂无数据</p>;
  }

  let min = Math.min(...valid);
  let max = Math.max(...valid);
  if (refLine !== undefined) {
    min = Math.min(min, refLine);
    max = Math.max(max, refLine);
  }
  const span = max - min || 1;
  min -= span * 0.06;
  max += span * 0.06;

  const n = labels.length;
  const x = (i: number) => PAD_L + (i * (VIEW_W - PAD_L - PAD_R)) / Math.max(n - 1, 1);
  const y = (v: number) =>
    PAD_T + ((max - v) * (VIEW_H - PAD_T - PAD_B)) / (max - min);

  const yTicks = niceTicks(min, max);
  const xTickIdx = [0, Math.floor((n - 1) / 2), n - 1];

  return (
    <figure className="chart-box" style={height ? { height } : undefined}>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} role="img" aria-label="折线图">
        {yTicks.map((t) => (
          <g key={t}>
            <line
              x1={PAD_L}
              x2={VIEW_W - PAD_R}
              y1={y(t)}
              y2={y(t)}
              className="chart-grid"
            />
            <text x={PAD_L - 8} y={y(t) + 4} textAnchor="end" className="chart-tick">
              {yFormat(t)}
            </text>
          </g>
        ))}
        {refLine !== undefined && (
          <line
            x1={PAD_L}
            x2={VIEW_W - PAD_R}
            y1={y(refLine)}
            y2={y(refLine)}
            className="chart-refline"
          />
        )}
        {xTickIdx.map((i) => (
          <text key={i} x={x(i)} y={VIEW_H - 8} textAnchor="middle" className="chart-tick">
            {labels[i]}
          </text>
        ))}
        {series.map((s) => (
          <polyline
            key={s.name}
            className="chart-line"
            fill="none"
            stroke={s.color}
            points={s.values
              .map((v, i) => (Number.isFinite(v) ? `${x(i)},${y(v)}` : ""))
              .filter(Boolean)
              .join(" ")}
          />
        ))}
      </svg>
      <figcaption className="chart-legend">
        {series.map((s) => (
          <span key={s.name}>
            <i style={{ background: s.color }} aria-hidden="true" />
            {s.name}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
