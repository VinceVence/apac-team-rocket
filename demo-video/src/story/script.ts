import story from "../../story-v2.json";
import timing from "./timing.json";

export type Speaker = "narrator" | "scammer" | "ana" | "jun";
export type Word = { t: string; s: number; e: number };
export type Line = {
  scene: string;
  speaker: Speaker;
  at: number;
  duration: number;
  words: Word[];
};
export const FPS = story.fps;
export const SCENES = story.scenes;
export const ESTIMATED: boolean = timing.estimated;
export const LINES: Record<string, Line> = timing.lines as unknown as Record<string, Line>;
export const sceneStart = (scene: string) =>
  SCENES.find((s) => s.id === scene)!.start;
export const sceneLines = (scene: string) =>
  Object.entries(LINES)
    .filter(([, l]) => l.scene === scene)
    .map(([id, l]) => ({ ...l, id }));

/** Scene-local start (s) of a line. */
export const at = (id: string) => LINES[id].at;
/** Scene-local end (s) of a line. */
export const end = (id: string) => LINES[id].at + LINES[id].duration;
const clean = (s: string) => s.toLowerCase().replace(/[^a-z0-9-]/g, "");
const find = (id: string, prefix: string, nth: number) => {
  const words = LINES[id].words;
  const tries = [clean(prefix), clean(prefix).split("-")[0]];
  for (const p of tries) {
    const ws = words.filter((w) => clean(w.t).startsWith(p));
    if (ws.length) return ws[Math.min(nth, ws.length - 1)];
  }
  // Never crash a render over a cue: fall back to the line start.
  console.warn(`No word "${prefix}" in line ${id}; using line start`);
  return { t: prefix, s: LINES[id].at, e: LINES[id].at + 0.3 };
};
/** Scene-local start (s) of the first word in a line that starts with `prefix` (nth match). */
export const word = (id: string, prefix: string, nth = 0) => find(id, prefix, nth).s;
export const wordEnd = (id: string, prefix: string, nth = 0) => find(id, prefix, nth).e;
/** Is this line being spoken at scene-local time t? */
export const speaking = (id: string, t: number) => t >= at(id) && t <= end(id);
