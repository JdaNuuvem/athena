"use client";

import { useState } from "react";

interface HelpTooltipProps {
  text: string;
  children?: React.ReactNode;
  position?: "top" | "bottom" | "left" | "right";
}

export default function HelpTooltip({ text, children, position = "top" }: HelpTooltipProps) {
  const [show, setShow] = useState(false);

  const posClasses = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  return (
    <span className="relative inline-flex items-center" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children || <span className="inline-flex items-center justify-center w-4 h-4 text-[9px] font-bold rounded-full bg-neutral-700 text-neutral-400 hover:bg-indigo-600 hover:text-white cursor-help transition-colors ml-1">?</span>}
      {show && (
        <span className={"absolute z-50 px-2 py-1.5 text-[10px] leading-relaxed text-neutral-200 bg-neutral-850 border border-neutral-600 rounded-lg shadow-xl whitespace-nowrap pointer-events-none " + posClasses[position]}>
          {text}
        </span>
      )}
    </span>
  );
}

/** Inline text with ? tooltip — wraps a label and adds the ? icon after it. */
export function LabelWithHelp({ label, help, className = "" }: { label: string; help: string; className?: string }) {
  return (
    <span className={"inline-flex items-center gap-1 " + className}>
      <span>{label}</span>
      <HelpTooltip text={help} />
    </span>
  );
}
