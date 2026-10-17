import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { continueRender, delayRender, useCurrentFrame } from "remotion";
import { paintTown, paintWater } from "./art/town-art.js";
import { drawResident } from "./art/resident-sprites.js";
import "../design";

type Point = [number, number];
const routes: Point[][] = [
  [
    [150, 260],
    [315, 260],
    [315, 310],
    [150, 310],
    [150, 260],
  ],
  [
    [480, 260],
    [690, 260],
    [690, 310],
    [555, 310],
    [555, 346],
    [405, 346],
    [405, 310],
    [315, 310],
    [315, 260],
    [480, 260],
  ],
  [
    [315, 310],
    [315, 485],
    [480, 485],
    [690, 485],
    [820, 485],
    [690, 485],
    [690, 310],
    [555, 310],
    [555, 346],
    [405, 346],
    [405, 310],
    [315, 310],
  ],
];
function walk(path: Point[], distance: number) {
  const lengths = path
    .slice(1)
    .map((p, i) => Math.hypot(p[0] - path[i][0], p[1] - path[i][1]));
  let d = distance % lengths.reduce((a, b) => a + b, 0);
  for (let i = 0; i < lengths.length; i++) {
    if (d <= lengths[i]) {
      const p = path[i],
        q = path[i + 1],
        v = d / lengths[i];
      return {
        x: p[0] + (q[0] - p[0]) * v,
        y: p[1] + (q[1] - p[1]) * v,
        direction:
          Math.abs(q[0] - p[0]) > 1
            ? q[0] > p[0]
              ? "right"
              : "left"
            : q[1] > p[1]
              ? "down"
              : "up",
      };
    }
    d -= lengths[i];
  }
  return { x: path[0][0], y: path[0][1], direction: "down" };
}
const bubble = (
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  bg = "#fff8df",
  fg = "#244e35",
) => {
  ctx.font = '600 14px "DM Sans",sans-serif';
  ctx.textAlign = "center";
  const w = ctx.measureText(text).width + 20;
  ctx.fillStyle = "#173d2928";
  ctx.beginPath();
  ctx.roundRect(x - w / 2 + 2, y - 23 + 2, w, 28, 6);
  ctx.fill();
  ctx.fillStyle = bg;
  ctx.beginPath();
  ctx.roundRect(x - w / 2, y - 23, w, 28, 6);
  ctx.fill();
  ctx.fillStyle = fg;
  ctx.fillText(text, x, y - 4);
};

export const Town: React.FC<{
  time: number;
  zoom?: number;
  cx?: number;
  cy?: number;
  mode?: "day" | "scam" | "panic" | "protect" | "calm";
  dark?: number;
  /** Name tags above the two story residents. */
  tags?: { C001?: string; C002?: string };
  /** 0..1: draw the glowing payment trails ("every payment leaves a trail"). */
  trails?: number;
  /** CSS filter on the canvas, e.g. "grayscale(0.7)". */
  filter?: string;
  /** Hide the built-in money bubbles (day/calm). */
  quiet?: boolean;
  anaPosition?: { x: number; y: number; direction: string };
}> = ({
  time,
  zoom = 1,
  cx = 480,
  cy = 300,
  mode = "day",
  dark = 0,
  tags,
  trails = 0,
  filter,
  quiet = false,
  anaPosition,
}) => {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [handle] = useState(() => delayRender("Draw original town assets"));
  const [ready, setReady] = useState(false);
  const released = useRef(false);
  const f = useCurrentFrame();
  useEffect(() => {
    let on = true;
    document.fonts.ready.then(() => {
      if (on) setReady(true);
    });
    return () => {
      on = false;
    };
  }, []);
  useLayoutEffect(() => {
    if (!ready || !canvas.current) return;
    const ctx = canvas.current.getContext("2d")!;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#173c2a";
    ctx.fillRect(0, 0, 1920, 1080);
    ctx.save();
    ctx.translate(960, 540);
    ctx.scale(2 * zoom, 2 * zoom);
    ctx.translate(-cx, -cy);
    ctx.imageSmoothingEnabled = false;
    paintTown(ctx);
    paintWater(ctx, time * 1000, true);
    const actors = Array.from({ length: 29 }, (_, i) => ({
      id: "C" + String(i + 3).padStart(3, "0"),
      ...walk(routes[i % 3], time * 13 + i * 61),
    }));
    actors.push(
      {
        id: "C001",
        x: anaPosition?.x ?? 600,
        y: anaPosition?.y ?? 485,
        direction: anaPosition?.direction ?? "down",
      },
      { id: "C002", x: 315, y: 310, direction: "down" },
    );
    if (trails > 0) {
      ctx.save();
      ctx.lineCap = "round";
      routes.forEach((r, ri) => {
        const total = r
          .slice(1)
          .reduce(
            (a, p, i) => a + Math.hypot(p[0] - r[i][0], p[1] - r[i][1]),
            0,
          );
        ctx.setLineDash([2, 7]);
        ctx.lineDashOffset = -time * 30;
        ctx.strokeStyle = ["#ffe9a8", "#b8f2cf", "#ffd0a8"][ri];
        ctx.globalAlpha = 0.85;
        ctx.lineWidth = 3;
        ctx.shadowColor = ctx.strokeStyle;
        ctx.shadowBlur = 8;
        ctx.beginPath();
        let left = total * Math.min(1, trails * (1 + ri * 0.15));
        ctx.moveTo(r[0][0], r[0][1]);
        for (let i = 1; i < r.length && left > 0; i++) {
          const [x0, y0] = r[i - 1];
          const [x1, y1] = r[i];
          const seg = Math.hypot(x1 - x0, y1 - y0);
          const v = Math.min(1, left / seg);
          ctx.lineTo(x0 + (x1 - x0) * v, y0 + (y1 - y0) * v);
          left -= seg;
        }
        ctx.stroke();
      });
      ctx.restore();
    }
    actors.sort((a, b) => a.y - b.y);
    for (const a of actors) {
      const upset = a.id === "C001" && mode === "panic";
      const lift = upset ? Math.max(0, Math.sin(time * 12)) * 14 : 0;
      if (
        (a.id === "C001" && (mode === "scam" || mode === "panic")) ||
        (a.id === "C002" && mode === "protect")
      ) {
        ctx.strokeStyle = upset ? "#ffd5a5" : "#f9f6c5";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.ellipse(a.x, a.y + 1, 16, 6, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
      drawResident(
        ctx,
        a.x,
        a.y - 25 - lift,
        a.id,
        a.direction,
        Math.floor(time * 7 + Number(a.id.slice(1))) % 4,
        a.id === "C001" || a.id === "C002",
        upset,
      );
    }
    if (!quiet && (mode === "day" || mode === "calm")) {
      const phase = time % 17;
      if (phase < 6) bubble(ctx, "Coffee · ₱65", 150, 240);
      if (phase > 3 && phase < 12) bubble(ctx, "Groceries · ₱120", 150, 456);
      if (phase > 9) bubble(ctx, "Sent home · ₱500", 480, 457);
      for (let i = 0; i < 6; i++) {
        const x = 120 + i * 120;
        const y = 280 + Math.sin(time * 1.4 + i) * 4;
        ctx.fillStyle = "#fff6c0";
        ctx.beginPath();
        ctx.arc(x + Math.sin(time + i) * 20, y, 2.2, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    if (mode === "scam" && time > 27 && !quiet)
      bubble(ctx, "Sent · ₱900", 600, 440, "#fff0ce", "#903c2f");
    if (mode === "panic") {
      const jump = Math.max(0, Math.sin(time * 12)) * 14;
      ctx.fillStyle = "#b84d34";
      ctx.beginPath();
      ctx.arc(600, 420 - jump, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#fff8db";
      ctx.font = '700 19px "DM Sans",sans-serif';
      ctx.textAlign = "center";
      ctx.fillText("!", 600, 427 - jump);
      bubble(ctx, "HELP! My money!", 600, 392 - jump, "#fff0cf", "#8c3c29");
    }
    if (mode === "protect") {
      const lift = Math.sin(time * 4) * 3;
      ctx.fillStyle = "#2a7951";
      ctx.beginPath();
      ctx.moveTo(302, 242 + lift);
      ctx.lineTo(328, 242 + lift);
      ctx.lineTo(326, 262 + lift);
      ctx.lineTo(315, 273 + lift);
      ctx.lineTo(304, 262 + lift);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = "#e8f3c5";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "#fff7d7";
      ctx.font = '700 21px "DM Sans",sans-serif';
      ctx.textAlign = "center";
      ctx.fillText("✓", 315, 263 + lift);
      if (!quiet) {
        bubble(
          ctx,
          "Stopped before debit",
          315,
          226 + lift,
          "#ddf6c8",
          "#205b3e",
        );
        bubble(ctx, "Coffee · paid", 150, 240);
      }
    }
    if (tags) {
      if (tags.C001)
        bubble(
          ctx,
          tags.C001,
          anaPosition?.x ?? 600,
          (anaPosition?.y ?? 485) - 37,
          "#2f7a59",
          "#f2fff4",
        );
      if (tags.C002 && mode !== "protect")
        bubble(ctx, tags.C002, 315, 273, "#3c6c8c", "#f2f8ff");
    }
    ctx.restore();
    if (dark) {
      ctx.fillStyle = `rgba(7,26,26,${dark})`;
      ctx.fillRect(0, 0, 1920, 1080);
    }
    if (!released.current) {
      released.current = true;
      continueRender(handle);
    }
  }, [
    ready,
    time,
    zoom,
    cx,
    cy,
    mode,
    dark,
    f,
    handle,
    tags,
    trails,
    quiet,
    anaPosition,
  ]);
  return (
    <canvas
      ref={canvas}
      width={1920}
      height={1080}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        filter,
      }}
    />
  );
};

export const Portrait: React.FC<{
  id?: string;
  upset?: boolean;
  size?: number;
  closeup?: boolean;
}> = ({ id = "C001", upset = false, size = 260, closeup = false }) => {
  const ref = useRef<HTMLCanvasElement>(null);
  const f = useCurrentFrame();
  useLayoutEffect(() => {
    const ctx = ref.current!.getContext("2d")!;
    ctx.clearRect(0, 0, 70, 90);
    drawResident(
      ctx,
      closeup ? 20 : 35,
      (closeup ? 20 : 35) - (upset ? Math.max(0, Math.sin(f / 4)) * 6 : 0),
      id,
      "down",
      Math.floor(f / 5) % 4,
      true,
      upset,
    );
  }, [f, id, upset, closeup]);
  return (
    <canvas
      ref={ref}
      width={closeup ? 40 : 70}
      height={closeup ? 50 : 90}
      style={{
        width: size,
        height: closeup ? size * 1.25 : (size * 90) / 70,
        imageRendering: "pixelated",
      }}
    />
  );
};
