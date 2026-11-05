import { useEffect, useRef, useState } from "react";

interface CountUpProps {
  value: number;
  format: (value: number) => string;
}

/** 数字从当前值滚动到目标值，用于统计卡入场动画。 */
export function CountUp({ value, format }: CountUpProps) {
  const [display, setDisplay] = useState(0);
  const currentRef = useRef(0);

  useEffect(() => {
    if (typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      currentRef.current = value;
      setDisplay(value);
      return;
    }
    const from = currentRef.current;
    if (from === value) {
      return;
    }
    const duration = 700;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next = from + (value - from) * eased;
      currentRef.current = next;
      setDisplay(next);
      if (progress < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        currentRef.current = value;
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return <>{format(display)}</>;
}
