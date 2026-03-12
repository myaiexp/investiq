import "./SparklineChart.css";

interface SparklineChartProps {
  data: { time: number; value: number }[];
  width?: number;
  height?: number;
  color?: string;
}

export default function SparklineChart({
  data,
  width = 120,
  height = 32,
  color = "var(--accent)",
}: SparklineChartProps) {
  if (data.length < 2) return null;

  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      className="sparkline-chart"
      viewBox={`0 0 ${width} ${height}`}
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
