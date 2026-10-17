import React from "react";
import {
  AbsoluteFill,
  CanvasImage,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { C, Icon } from "../design";
export { C, Icon };
export const fade = (f: number, a: number, b: number) =>
  interpolate(f, [a, b], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
export const useStorySeconds = () => useCurrentFrame() / useVideoConfig().fps;
export const StoryFrame: React.FC<{
  children: React.ReactNode;
  label?: string;
  brand?: "town" | "product";
}> = ({ children, label = "", brand = "product" }) => (
  <AbsoluteFill
    style={{
      fontFamily: "DM Sans, Arial, sans-serif",
      color: "#fff9e9",
      background: "#112d24",
      overflow: "hidden",
    }}
  >
    {children}
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        background:
          "radial-gradient(ellipse at center,transparent 45%,#08201970 100%)",
      }}
    />
    <div
      style={{
        position: "absolute",
        left: 42,
        right: 42,
        top: 30,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        fontSize: 17,
        textShadow: "0 2px 8px #071e17",
      }}
    >
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          fontWeight: 600,
        }}
      >
        {brand === "town" ? (
          <CanvasImage
            src={staticFile("mark.svg")}
            style={{ width: 28, height: 28 }}
          />
        ) : (
          <Icon size={28} />
        )}
        {brand === "town" ? "MINT TOWN" : "RESOLUTION AGENT"}
      </span>
      <span>{label}</span>
    </div>
  </AbsoluteFill>
);

export const Float: React.FC<{
  children: React.ReactNode;
  at?: number;
  style?: React.CSSProperties;
}> = ({ children, at = 0, style }) => {
  const f = useCurrentFrame();
  const p = fade(f, at, at + 18);
  return (
    <div
      style={{
        opacity: p,
        transform: `translateY(${(1 - p) * 24}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
export const Speech: React.FC<{
  children: React.ReactNode;
  x: number;
  y: number;
  w?: number;
  at?: number;
  dark?: boolean;
}> = ({ children, x, y, w = 520, at = 0, dark = false }) => (
  <Float
    at={at}
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: w,
      background: dark ? "#173c2cf2" : "#fffaeaf5",
      color: dark ? "#f5f7ed" : "#203d2d",
      padding: "24px 30px",
      borderRadius: 22,
      fontSize: 32,
      lineHeight: 1.35,
      boxShadow: "0 14px 50px #08281f45",
    }}
  >
    {children}
    <div
      style={{
        position: "absolute",
        bottom: -17,
        left: 42,
        width: 28,
        height: 28,
        background: "inherit",
        transform: "rotate(45deg)",
      }}
    />
  </Float>
);
export const Phone: React.FC<{
  children: React.ReactNode;
  title?: string;
  x?: number;
  y?: number;
  width?: number;
  alarm?: boolean;
}> = ({
  children,
  title = "Mint Town wallet",
  x = 1150,
  y = 130,
  width = 580,
  alarm = false,
}) => {
  const f = useCurrentFrame();
  return (
    <Float
      at={5}
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        height: 790,
        background: "#f9faef",
        color: C.ink,
        borderRadius: 46,
        border: `12px solid ${alarm ? "#57342d" : "#183d2e"}`,
        boxShadow: "0 30px 100px #071f2766",
        transform: `rotate(${alarm && f < 80 ? Math.sin(f * 1.8) * 1.2 : 0}deg)`,
      }}
    >
      <div
        style={{
          width: 115,
          height: 25,
          borderRadius: 18,
          background: "#183d2e",
          margin: "12px auto 20px",
        }}
      />
      <div
        style={{
          fontSize: 24,
          fontWeight: 700,
          padding: "14px 28px 20px",
          borderBottom: "1px solid #d7e2d2",
        }}
      >
        {title}
      </div>
      <div style={{ padding: 28 }}>{children}</div>
      <div
        style={{
          position: "absolute",
          bottom: 15,
          left: "37%",
          width: "26%",
          height: 5,
          background: "#b8c8b8",
          borderRadius: 5,
        }}
      />
    </Float>
  );
};

export const Paper: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  rotate?: number;
}> = ({ children, style, rotate = -2 }) => (
  <div
    style={{
      background: "#fffaf0",
      color: C.ink,
      padding: 45,
      boxShadow: "0 25px 80px #0319145c",
      transform: `rotate(${rotate}deg)`,
      borderRadius: 6,
      ...style,
    }}
  >
    {children}
  </div>
);
export const Stamp: React.FC<{
  text: string;
  at: number;
  color?: string;
  x?: number;
  y?: number;
}> = ({ text, at, color = "#246e4d", x = 1180, y = 650 }) => {
  const f = useCurrentFrame();
  const p = fade(f, at, at + 8);
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        opacity: p,
        transform: `scale(${1.5 - 0.5 * p}) rotate(-12deg)`,
        border: `6px solid ${color}`,
        borderRadius: 12,
        padding: "14px 24px",
        fontSize: 47,
        fontWeight: 700,
        color,
        letterSpacing: 2,
      }}
    >
      {text}
    </div>
  );
};

export const TokenPath: React.FC<{
  at: number;
  duration: number;
  points: string;
  color?: string;
  from?: [number, number];
  to?: [number, number];
}> = ({
  at,
  duration,
  points,
  color = "#d5f5b9",
  from = [0, 0],
  to = [1, 1],
}) => {
  const f = useCurrentFrame();
  const p = fade(f, at, at + duration);
  return (
    <svg
      style={{
        position: "absolute",
        inset: 0,
        width: 1920,
        height: 1080,
        overflow: "visible",
      }}
    >
      <path
        d={points}
        stroke={color}
        fill="none"
        strokeWidth={4}
        strokeDasharray="8 10"
        opacity={p > 0.01 ? 0.65 : 0}
      />
      <circle
        cx={from[0] + (to[0] - from[0]) * p}
        cy={from[1] + (to[1] - from[1]) * p}
        r={10}
        fill={color}
        opacity={p > 0 && p < 1 ? 1 : 0}
      />
    </svg>
  );
};
