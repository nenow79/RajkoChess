const WIDTH = 450;
const HEIGHT = 116;
const PAD_X = 12;
const PAD_Y = 12;
const MAX_EVAL = 10;

const clamp = (value) => Math.max(-MAX_EVAL, Math.min(MAX_EVAL, value));

export default function EvaluationChart({ data, currentPly, onNavigate }) {
  if (!data?.length) return null;

  const plotWidth = WIDTH - PAD_X * 2;
  const plotHeight = HEIGHT - PAD_Y * 2;
  const zeroY = PAD_Y + plotHeight / 2;
  const lastPly = Math.max(data.at(-1).ply, 1);
  const xFor = (ply) => PAD_X + (ply / lastPly) * plotWidth;
  const yFor = (evaluation) => zeroY - (clamp(evaluation) / MAX_EVAL) * (plotHeight / 2);
  const linePoints = data.map((point) => `${xFor(point.ply)},${yFor(point.evaluation)}`).join(" ");
  const areaPoints = `${PAD_X},${zeroY} ${linePoints} ${xFor(lastPly)},${zeroY}`;
  const activePoint = data.find((point) => point.ply === currentPly);
  const hitWidth = plotWidth / Math.max(data.length - 1, 1);

  return (
    <div className="evaluation-chart">
      <div className="evaluation-chart-header">
        <strong>Przebieg oceny Stockfisha</strong>
        <span>kliknij wykres, aby przejść do ruchu</span>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Wykres oceny partii">
        <defs>
          <clipPath id="positive-evaluation">
            <rect x="0" y="0" width={WIDTH} height={zeroY} />
          </clipPath>
          <clipPath id="negative-evaluation">
            <rect x="0" y={zeroY} width={WIDTH} height={HEIGHT - zeroY} />
          </clipPath>
        </defs>

        <polygon points={areaPoints} className="evaluation-area positive" clipPath="url(#positive-evaluation)" />
        <polygon points={areaPoints} className="evaluation-area negative" clipPath="url(#negative-evaluation)" />
        <line x1={PAD_X} y1={zeroY} x2={WIDTH - PAD_X} y2={zeroY} className="evaluation-zero" />
        <polyline points={linePoints} className="evaluation-line" />

        {activePoint && (
          <>
            <line
              x1={xFor(activePoint.ply)}
              y1={PAD_Y}
              x2={xFor(activePoint.ply)}
              y2={HEIGHT - PAD_Y}
              className="evaluation-active-line"
            />
            <circle
              cx={xFor(activePoint.ply)}
              cy={yFor(activePoint.evaluation)}
              r="4"
              className="evaluation-active-point"
            />
          </>
        )}

        {data.map((point) => (
          <rect
            key={point.ply}
            x={xFor(point.ply) - hitWidth / 2}
            y={0}
            width={hitWidth}
            height={HEIGHT}
            className="evaluation-hit-area"
            onClick={() => onNavigate(point.ply)}
          >
            <title>{point.move_label}: {point.evaluation > 0 ? "+" : ""}{point.evaluation.toFixed(2)}</title>
          </rect>
        ))}

        <text x={PAD_X} y={HEIGHT - 2} className="evaluation-axis-label">0</text>
        <text x={WIDTH / 2} y={HEIGHT - 2} className="evaluation-axis-label" textAnchor="middle">
          {Math.ceil(lastPly / 4)}
        </text>
        <text x={WIDTH - PAD_X} y={HEIGHT - 2} className="evaluation-axis-label" textAnchor="end">
          {Math.ceil(lastPly / 2)}
        </text>
      </svg>
    </div>
  );
}
