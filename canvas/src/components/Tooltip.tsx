"use client";

import { useState, useRef, useEffect, type ReactNode } from "react";

interface Props {
  text: string;
  children: ReactNode;
}

export function Tooltip({ text, children }: Props) {
  const [show, setShow] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Clean up timer on unmount
  useEffect(() => () => clearTimeout(timerRef.current), []);

  const enter = () => {
    timerRef.current = setTimeout(() => setShow(true), 400);
  };
  const leave = () => {
    clearTimeout(timerRef.current);
    setShow(false);
  };

  return (
    <div className="relative" onMouseEnter={enter} onMouseLeave={leave}>
      {children}
      {show && text && (
        <div className="absolute z-[100] bottom-full left-0 mb-1 max-w-[350px] max-h-[200px] overflow-y-auto px-3 py-2 bg-zinc-800 border border-zinc-600 rounded-lg shadow-xl shadow-black/40 pointer-events-none">
          <div className="text-[10px] text-zinc-200 whitespace-pre-wrap break-words leading-relaxed">
            {text}
          </div>
        </div>
      )}
    </div>
  );
}
