import React from "react";
import {
  AbsoluteFill,
  interpolate,
  random,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";
import { C } from "./Visuals";

export const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;
/** 0..1 between seconds a and b. */
export const ramp = (t: number, a: number, b: number, ease = true) =>
  interpolate(t, [a, b], [0, 1], {
    ...clamp,
    easing: ease ? Easing.bezier(0.22, 1, 0.36, 1) : undefined,
  });
/** Snappy overshoot spring-ish 0..1 for pops. */
export const pop = (t: number, a: number, d = 0.45) =>
  interpolate(t, [a, a + d * 0.6, a + d], [0, 1.08, 1], clamp);

export const useT = () => useCurrentFrame() / useVideoConfig().fps;

// Cache a small texture instead of recalculating full-HD SVG turbulence on every frame.
const grainTexture =
  'url("data:image/svg+xml,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="7"/><feColorMatrix type="saturate" values="0"/></filter><rect width="128" height="128" filter="url(#n)"/></svg>',
  ) +
  '")';

/** A light static texture keeps the small submission export clean. */
export const Grain: React.FC<{ amount?: number }> = ({ amount = 0.07 }) => {
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        mixBlendMode: "overlay",
        opacity: amount * 0.35,
        backgroundImage: grainTexture,
        backgroundPosition: "0 0",
      }}
    />
  );
};

/** A short, cue-locked accent on the thing that just changed. */
export const Highlight: React.FC<{
  at: number; x: number; y: number; width: number; height: number; color?: string;
}> = ({ at, x, y, width, height, color = C.mint }) => {
  const t = useT();
  const p = ramp(t, at, at + 0.75);
  if (t < at || t > at + 0.75) return null;
  return <div style={{ position: "absolute", left: x - p * 16, top: y - p * 16,
    width: width + p * 32, height: height + p * 32, boxSizing: "border-box",
    border: "3px solid " + color, borderRadius: 30, opacity: 1 - p,
    boxShadow: "0 0 32px " + color + "55", pointerEvents: "none" }} />;
};

/** Fade from / to black at scene edges (seconds). */
export const Dip: React.FC<{
  inFor?: number;
  outFor?: number;
  duration: number;
  color?: string;
}> = ({ inFor = 0, outFor = 0, duration, color = "#030c09" }) => {
  const t = useT();
  const a = Math.max(
    inFor > 0 ? 1 - ramp(t, 0, inFor, false) : 0,
    outFor > 0 ? ramp(t, duration - outFor, duration, false) : 0,
  );
  if (a <= 0) return null;
  return <AbsoluteFill style={{ background: color, opacity: a }} />;
};

/** Camera shake: decaying jitter after each hit time. */
export const useShake = (hits: number[], strength = 14, decay = 7) => {
  const t = useT();
  let x = 0,
    y = 0,
    r = 0;
  for (const h of hits) {
    const d = t - h;
    if (d >= 0 && d < 0.8) {
      const k = Math.exp(-d * decay) * strength;
      const s = Math.floor(t * 60);
      x += (random(`x${h}${s}`) - 0.5) * 2 * k;
      y += (random(`y${h}${s}`) - 0.5) * 2 * k;
      r += (random(`r${h}${s}`) - 0.5) * 0.12 * k;
    }
  }
  return `translate(${x}px, ${y}px) rotate(${r}deg)`;
};

/** White/colored flash that decays from time `at`. */
export const Flash: React.FC<{
  at: number;
  color?: string;
  peak?: number;
  len?: number;
}> = ({ at, color = "#ffffff", peak = 0.85, len = 0.5 }) => {
  const t = useT();
  const d = t - at;
  if (d < 0 || d > len) return null;
  return (
    <AbsoluteFill
      style={{
        background: color,
        opacity: peak * (1 - d / len) ** 2,
        pointerEvents: "none",
      }}
    />
  );
};

/** Pulsing red vignette (dread). intensity 0..1 */
export const Dread: React.FC<{ intensity: number; bpm?: number }> = ({
  intensity,
  bpm = 80,
}) => {
  const t = useT();
  const beat = (t * bpm) / 60;
  const pulse = Math.exp(-((beat % 1) * 6));
  if (intensity <= 0) return null;
  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        background: `radial-gradient(ellipse at center, transparent 38%, rgba(120,18,10,${
          (0.35 + 0.35 * pulse) * intensity
        }) 100%)`,
      }}
    />
  );
};

/** Animated voice waveform bars. */
export const Waveform: React.FC<{
  active: boolean;
  color?: string;
  bars?: number;
  height?: number;
}> = ({ active, color = "#a8412f", bars = 26, height = 70 }) => {
  const f = useCurrentFrame();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5, height }}>
      {Array.from({ length: bars }, (_, i) => {
        const v = active
          ? 0.2 +
            0.8 *
              Math.abs(
                Math.sin(f * 0.45 + i * 0.9) * Math.sin(f * 0.17 + i * 0.37),
              )
          : 0.08;
        return (
          <div
            key={i}
            style={{
              width: 7,
              height: height * v,
              borderRadius: 4,
              background: color,
              opacity: active ? 0.9 : 0.35,
            }}
          />
        );
      })}
    </div>
  );
};

/** Typewriter: reveal text between seconds a and b. */
export const typed = (text: string, t: number, a: number, b: number) =>
  text.slice(0, Math.round(text.length * ramp(t, a, b, false)));

/** Big kicker label used for section titles. */
export const Kicker: React.FC<{
  children: React.ReactNode;
  color?: string;
}> = ({ children, color = C.mint }) => (
  <div style={{ fontSize: 24, letterSpacing: 5, fontWeight: 600, color }}>
    {children}
  </div>
);

/** Chapter card that slides in from the left in the top-left corner. */
export const Chapter: React.FC<{
  n: string;
  title: string;
  at?: number;
  until?: number;
}> = ({ n, title, at = 0.15, until = 3.4 }) => {
  const t = useT();
  const p = ramp(t, at, at + 0.6) * (1 - ramp(t, until, until + 0.5));
  if (p <= 0) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: 64,
        top: 84,
        display: "flex",
        alignItems: "center",
        gap: 16,
        opacity: p,
        transform: `translateX(${(1 - p) * -40}px)`,
        textShadow: "0 3px 14px #04140f",
      }}
    >
      <span
        style={{
          fontSize: 20,
          fontWeight: 700,
          color: "#0c2a20",
          background: C.mint,
          borderRadius: 6,
          padding: "4px 10px",
          letterSpacing: 2,
        }}
      >
        {n}
      </span>
      <span style={{ fontSize: 26, fontWeight: 600, letterSpacing: 1 }}>
        {title}
      </span>
    </div>
  );
};
