import "./PriceChange.css";

interface PriceChangeProps {
  value: number;
  size?: "sm" | "md";
}

export default function PriceChange({ value, size = "md" }: PriceChangeProps) {
  const isPositive = value > 0;
  const isZero = value === 0;
  const arrow = isZero ? "" : isPositive ? "\u25B2" : "\u25BC";
  const colorClass = isZero
    ? "price-change--neutral"
    : isPositive
      ? "price-change--up"
      : "price-change--down";

  return (
    <span className={`price-change price-change--${size} ${colorClass} number`}>
      {arrow} {value > 0 ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}
