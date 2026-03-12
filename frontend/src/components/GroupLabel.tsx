import type { ReactNode } from "react";
import "./GroupLabel.css";

interface GroupLabelProps {
  children: ReactNode;
}

export default function GroupLabel({ children }: GroupLabelProps) {
  return <h3 className="group-label">{children}</h3>;
}
