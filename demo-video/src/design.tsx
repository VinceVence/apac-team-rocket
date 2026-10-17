import React from "react";
import {
  AbsoluteFill,
  CanvasImage,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Video } from "@remotion/media";
import "./style.css";

if (typeof document !== "undefined") {
  const handle = delayRender("Load bundled DM Sans");
  Promise.all(
    [400, 500, 600, 700].map(async (weight) => {
      const face = new FontFace(
        "DM Sans",
        `url(${staticFile(`fonts/dm-sans-${weight}.ttf`)})`,
        { weight: String(weight) },
      );
      document.fonts.add(await face.load());
    }),
  )
    .then(() => continueRender(handle))
    .catch((error) => {
      console.error(error);
      continueRender(handle);
    });
}

export const C = {
  forest: "#102e25",
  deep: "#082219",
  mint: "#b8f2cf",
  green: "#287653",
  paper: "#f5f7ee",
  ink: "#173a2c",
  dim: "#688475",
  lime: "#e5f5a5",
  amber: "#ffce88",
  red: "#e7a493",
};
export const ease = (f: number, start = 0, end = 22) =>
  interpolate(f, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
export const useSeconds = () => useCurrentFrame() / useVideoConfig().fps;

export const Icon: React.FC<{
  kind?: string;
  size?: number;
  color?: string;
}> = ({ kind = "agent", size = 54, color = "currentColor" }) => {
  const p: Record<string, React.ReactNode> = {
    agent: (
      <>
        <rect x="8" y="10" width="32" height="27" rx="8" />
        <path d="M24 4v6M18 20v6M30 20v6M18 32h12M4 18v12M44 18v8" />
        <circle cx="39" cy="37" r="7" />
        <path d="m44 42 4 4" />
      </>
    ),
    shield: (
      <>
        <path d="M24 4 43 11v14c0 11-19 21-19 21S5 36 5 25V11z" />
        <path d="m15 25 6 6 13-14" />
      </>
    ),
    person: (
      <>
        <circle cx="24" cy="14" r="9" />
        <path d="M8 45v-9c0-8 7-13 16-13s16 5 16 13v9M18 31l6 6 6-6" />
      </>
    ),
    data: (
      <>
        <ellipse cx="24" cy="10" rx="18" ry="6" />
        <path d="M6 10v27c0 9 36 9 36 0V10M6 23c0 9 36 9 36 0" />
      </>
    ),
    book: (
      <>
        <path d="M24 11c-8-7-19-5-19-5v33s11-2 19 5c8-7 19-5 19-5V6s-11-2-19 5v33M11 15h7M11 22h7M30 15h7M30 22h7" />
      </>
    ),
    model: (
      <>
        <path d="M7 42V6M7 42h36M14 30l8-11 9 5 10-15" />
        <circle cx="22" cy="19" r="3" />
        <circle cx="31" cy="24" r="3" />
      </>
    ),
    town: (
      <>
        <path d="m4 22 12-12 12 12M8 20v23h16V20M29 15l9-9 9 9M31 14v29h13V14M15 33v10M36 24h3M34 34h6" />
      </>
    ),
    check: <path d="m10 25 10 10 20-23" />,
    alert: (
      <>
        <path d="m24 5 21 37H3zM24 18v10" />
        <circle cx="24" cy="35" r="1" />
      </>
    ),
    lock: (
      <>
        <rect x="9" y="22" width="30" height="22" rx="5" />
        <path d="M15 22V12a9 9 0 0 1 18 0v10M24 30v6" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 50"
      fill="none"
      stroke={color}
      strokeWidth="2.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {p[kind] || p.agent}
    </svg>
  );
};

export const Badge: React.FC<{
  children: React.ReactNode;
  dark?: boolean;
  amber?: boolean;
}> = ({ children, dark = false, amber = false }) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      padding: "10px 16px",
      borderRadius: 50,
      background: amber ? C.amber : dark ? "#234a39" : "#deecdb",
      color: amber ? C.ink : dark ? C.mint : C.ink,
      fontSize: 22,
      fontWeight: 600,
      letterSpacing: 0.2,
    }}
  >
    {children}
  </div>
);

export const Reveal: React.FC<{
  children: React.ReactNode;
  delay?: number;
  style?: React.CSSProperties;
}> = ({ children, delay = 0, style }) => {
  const f = useCurrentFrame();
  const t = ease(f, delay, delay + 22);
  return (
    <div
      style={{
        opacity: t,
        transform: `translateY(${(1 - t) * 24}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

export const Chrome: React.FC<{
  children: React.ReactNode;
  dark?: boolean;
  chapter: string;
  index: number;
  duration: number;
}> = ({ children, dark = false, chapter, index, duration }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fill = Math.min(1, f / (duration * fps));
  return (
    <AbsoluteFill
      style={{
        background: dark ? C.forest : C.paper,
        color: dark ? C.paper : C.ink,
        fontFamily: "DM Sans, Arial, sans-serif",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.1,
          backgroundImage: `radial-gradient(${dark ? C.mint : C.green} 1px, transparent 1px)`,
          backgroundSize: "30px 30px",
          maskImage: "linear-gradient(90deg,transparent 45%,black)",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 38,
          left: 70,
          right: 70,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: 24,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            fontWeight: 700,
          }}
        >
          <CanvasImage
            src={staticFile("mark.svg")}
            style={{ width: 42, height: 42 }}
          />
          Mint Town
        </div>
        <span
          style={{
            fontSize: 19,
            letterSpacing: 2.5,
            textTransform: "uppercase",
            opacity: 0.65,
          }}
        >
          {chapter}
        </span>
        <div style={{ fontSize: 20, opacity: 0.65 }}>AI Builder Cup · BFSI</div>
      </div>
      {children}
      <div
        style={{
          position: "absolute",
          bottom: 23,
          left: 70,
          right: 70,
          display: "flex",
          justifyContent: "space-between",
          fontSize: 17,
          opacity: 0.6,
        }}
      >
        <span>
          Recorded Gemini run · Synthetic economy · Demo analyst approval
        </span>
        <span>TEAM ROCKET</span>
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 5,
          background: dark ? "#28483a" : "#d7e3d4",
        }}
      >
        <div
          style={{
            height: 5,
            width: `${((index + fill) / 12) * 100}%`,
            background: dark ? C.mint : C.green,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

export const Heading: React.FC<{
  eyebrow: string;
  children: React.ReactNode;
  light?: boolean;
  fontSize?: number;
}> = ({ eyebrow, children, light = false, fontSize = 68 }) => (
  <Reveal style={{ position: "absolute", left: 70, top: 126, right: 70 }}>
    <div
      style={{
        fontSize: 22,
        fontWeight: 600,
        letterSpacing: 3,
        textTransform: "uppercase",
        color: light ? C.mint : C.green,
        marginBottom: 14,
      }}
    >
      {eyebrow}
    </div>
    <div
      style={{
        fontSize,
        fontWeight: 700,
        lineHeight: 1.06,
        letterSpacing: -2.5,
      }}
    >
      {children}
    </div>
  </Reveal>
);

export const FilmFrame: React.FC<{
  file: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
  crop?: boolean;
}> = ({ file, x = 70, y = 280, w = 1150, h = 647, crop = false }) => {
  const regions: Record<string, number[]> = {
    "classifier-result.jpg": [110, 200, 1038, 560],
    "classifier-use.jpg": [110, 280, 1038, 400],
    "proposal.jpg": [110, 280, 1038, 420],
    "review.jpg": [1190, 300, 320, 250],
    "knowledge.jpg": [1190, 305, 320, 240],
  };
  const [sx, sy, sw, sh] = crop
    ? regions[file] || [105, 235, 1048, 500]
    : [0, 0, 1600, 900];
  const ratio = Math.min((w - 40) / sw, (h - 40) / sh);
  return (
    <Reveal
      delay={7}
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        height: h,
        borderRadius: 22,
        overflow: "hidden",
        boxShadow: "0 18px 60px #041a1c25",
        border: "1px solid #80a28c50",
        background: C.paper,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: (w - sw * ratio) / 2,
          top: (h - sh * ratio) / 2,
          width: sw * ratio,
          height: sh * ratio,
          overflow: "hidden",
        }}
      >
        <CanvasImage
          src={staticFile("footage/" + file)}
          style={{
            position: "absolute",
            width: 1600 * ratio,
            height: 900 * ratio,
            left: -sx * ratio,
            top: -sy * ratio,
            maxWidth: "none",
          }}
        />
      </div>
    </Reveal>
  );
};

export const TownClip: React.FC<{
  name: string;
  x?: number;
  y?: number;
  w?: number;
  h?: number;
}> = ({ name, x = 70, y = 295, w = 1130, h = 620 }) => {
  const { fps } = useVideoConfig();
  return (
    <Reveal
      delay={6}
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        height: h,
        borderRadius: 24,
        overflow: "hidden",
        border: "1px solid #71988170",
        boxShadow: "0 22px 80px #061d2926",
      }}
    >
      <Video
        src={staticFile(`footage/${name}.mp4`)}
        muted
        loop
        premountFor={fps}
        objectFit="cover"
        style={{ width: "100%", height: "100%" }}
      />
    </Reveal>
  );
};

export const Arrow: React.FC<{
  width?: number;
  color?: string;
  down?: boolean;
}> = ({ width = 70, color = C.green, down = false }) => (
  <svg
    width={down ? 30 : width}
    height={down ? width : 30}
    viewBox={`0 0 ${down ? 30 : width} ${down ? width : 30}`}
    style={{ flexShrink: 0 }}
  >
    <path
      d={
        down
          ? `M15 0V${width - 4}m-9-9 9 9 9-9`
          : `M0 15H${width - 4}m-9-9 9 9-9 9`
      }
      stroke={color}
      strokeWidth="3"
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

export const Receipt: React.FC<{
  label: string;
  value: string;
  note?: string;
  dark?: boolean;
}> = ({ label, value, note, dark }) => (
  <div
    style={{
      borderBottom: `1px solid ${dark ? "#54756066" : "#c6d4c6"}`,
      padding: "20px 0",
    }}
  >
    <div style={{ fontSize: 21, opacity: 0.7, marginBottom: 6 }}>{label}</div>
    <div style={{ fontSize: 34, fontWeight: 600, letterSpacing: -0.5 }}>
      {value}
    </div>
    {note && (
      <div style={{ fontSize: 19, opacity: 0.65, marginTop: 8 }}>{note}</div>
    )}
  </div>
);
