import type { ReactNode } from "react";
import "./CardGrid.css";

interface CardGridProps {
  children: ReactNode;
}

export default function CardGrid({ children }: CardGridProps) {
  return <div className="card-grid">{children}</div>;
}
