import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";

type StaggerFrom = "first" | "last" | "center" | number;

type RotatingTextProps = {
  texts: string[];
  mainClassName?: string;
  splitLevelClassName?: string;
  initial?: Record<string, unknown>;
  animate?: Record<string, unknown>;
  exit?: Record<string, unknown>;
  transition?: Record<string, unknown>;
  staggerDuration?: number;
  staggerFrom?: StaggerFrom;
  rotationInterval?: number;
};

function getDelays(length: number, staggerFrom: StaggerFrom, staggerDuration: number) {
  const indices = [...Array(length).keys()];

  if (staggerFrom === "last") {
    return indices.map((index) => (length - 1 - index) * staggerDuration);
  }

  if (staggerFrom === "center") {
    const center = (length - 1) / 2;
    return indices.map((index) => Math.abs(index - center) * staggerDuration);
  }

  if (typeof staggerFrom === "number") {
    return indices.map((index) => Math.abs(index - staggerFrom) * staggerDuration);
  }

  return indices.map((index) => index * staggerDuration);
}

export default function RotatingText({
  texts,
  mainClassName = "",
  splitLevelClassName = "",
  initial = { y: "100%" },
  animate = { y: 0 },
  exit = { y: "-120%" },
  transition = { type: "spring", damping: 30, stiffness: 400 },
  staggerDuration = 0.025,
  staggerFrom = "first",
  rotationInterval = 2000,
}: RotatingTextProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (texts.length <= 1) return undefined;
    const interval = window.setInterval(() => {
      setIndex((prev) => (prev + 1) % texts.length);
    }, rotationInterval);
    return () => window.clearInterval(interval);
  }, [rotationInterval, texts.length]);

  const activeText = texts[index] ?? "";
  const chars = useMemo(() => activeText.split(""), [activeText]);
  const delays = useMemo(
    () => getDelays(chars.length, staggerFrom, staggerDuration),
    [chars.length, staggerDuration, staggerFrom],
  );

  return (
    <span className={`inline-flex items-center ${mainClassName}`} aria-live="polite">
      <AnimatePresence mode="wait">
        <span key={activeText} className="inline-flex">
          {chars.map((char, charIndex) => (
            <span key={`${activeText}-${charIndex}`} className={splitLevelClassName}>
              <motion.span
                className="inline-block whitespace-pre"
                initial={initial}
                animate={animate}
                exit={exit}
                transition={{ ...transition, delay: delays[charIndex] }}
              >
                {char === " " ? "\u00A0" : char}
              </motion.span>
            </span>
          ))}
        </span>
      </AnimatePresence>
    </span>
  );
}
