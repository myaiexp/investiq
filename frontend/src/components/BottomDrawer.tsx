import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import "./BottomDrawer.css";

interface BottomDrawerProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export default function BottomDrawer({
  open,
  onClose,
  children,
}: BottomDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="bottom-drawer__overlay" onClick={onClose}>
      <div
        ref={drawerRef}
        className="bottom-drawer__panel"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="bottom-drawer__handle" />
        <div className="bottom-drawer__content">{children}</div>
      </div>
    </div>
  );
}
