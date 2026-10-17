import React from "react";
import {
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import { Audio } from "@remotion/media";
import { ESTIMATED, LINES, SCENES, sceneLines, type Speaker } from "./script";

const VOICE_GAIN: Record<Speaker, number> = {
  narrator: 1,
  scammer: 0.92,
  ana: 0.95,
  jun: 0.95,
};

/** Voice audio for every line in a scene. Silent while timing is only estimated. */
export const SceneVoice: React.FC<{ scene: string }> = ({ scene }) => {
  const { fps } = useVideoConfig();
  if (ESTIMATED) return null;
  return (
    <>
      {sceneLines(scene).map((l) => (
        <Sequence
          key={l.id}
          from={Math.round(l.at * fps)}
          name={`Voice · ${l.speaker} · ${l.id}`}
          premountFor={fps}
        >
          <Audio
            src={staticFile(`audio/story2/${l.id}.mp3`)}
            volume={VOICE_GAIN[l.speaker]}
          />
        </Sequence>
      ))}
    </>
  );
};

/** One-shot sound effect at scene-local second `at`. */
export const Sfx: React.FC<{
  name: string;
  at: number;
  volume?: number;
  rate?: number;
}> = ({ name, at, volume = 0.6, rate = 1 }) => {
  const { fps } = useVideoConfig();
  return (
    <Sequence
      from={Math.max(0, Math.round(at * fps))}
      name={`SFX · ${name}`}
      premountFor={fps}
    >
      <Audio
        src={staticFile(`audio/sfx/polished/${name}.wav`)}
        volume={volume}
        playbackRate={rate}
      />
    </Sequence>
  );
};

const SPEAKER_STYLE: Record<
  Speaker,
  { label?: string; color: string; chip: string; italic?: boolean }
> = {
  narrator: { color: "#fffaf0", chip: "" },
  scammer: {
    label: "CALLER",
    color: "#ffd2c4",
    chip: "#a8412f",
    italic: true,
  },
  ana: { label: "ANA", color: "#e9fbe9", chip: "#2f7a59" },
  jun: { label: "JUN", color: "#e9fbe9", chip: "#3c6c8c" },
};

/** Speaker-aware captions with the spoken word highlighted. */
export const SceneCaptions: React.FC<{ scene: string; bottom?: number }> = ({
  scene,
  bottom = 64,
}) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = f / fps;
  // Build caption pages: <= 7 words, break after sentence punctuation.
  const pages: {
    speaker: Speaker;
    words: { t: string; s: number; e: number }[];
  }[] = [];
  for (const l of sceneLines(scene)) {
    let cur: (typeof pages)[number] | null = null;
    for (const w of l.words) {
      if (!cur || cur.words.length >= 7) {
        cur = { speaker: l.speaker, words: [] };
        pages.push(cur);
      }
      cur.words.push(w);
      if (/[.?!]$/.test(w.t) && cur.words.length >= 3) cur = null;
    }
  }
  pages.sort((a, b) => a.words[0].s - b.words[0].s);
  const idx = pages.findIndex((p, i) => {
    const start = p.words[0].s - 0.08;
    const next = pages[i + 1]?.words[0].s ?? Infinity;
    const stop = Math.min(next - 0.04, p.words[p.words.length - 1].e + 0.5);
    return t >= start && t < stop;
  });
  if (idx < 0) return null;
  const page = pages[idx];
  const st = SPEAKER_STYLE[page.speaker];
  const pop = interpolate(t, [page.words[0].s - 0.08, page.words[0].s + 0.1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      data-video-captions
      style={{
        fontFamily: "DM Sans, Arial, sans-serif",
        position: "absolute",
        left: 0,
        right: 0,
        bottom,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 18,
          maxWidth: 1560,
          padding: "14px 28px",
          borderRadius: 18,
          background: "rgba(6,22,17,0.72)",
          backdropFilter: "blur(6px)",
          boxShadow: "0 10px 40px rgba(0,0,0,0.25)",
          opacity: pop,
          transform: `translateY(${(1 - pop) * 10}px)`,
        }}
      >
        {st.label && (
          <span
            style={{
              background: st.chip,
              color: "#fff",
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: 2,
              padding: "6px 12px",
              borderRadius: 8,
              flexShrink: 0,
            }}
          >
            {st.label}
          </span>
        )}
        <span
          style={{
            fontFamily: "DM Sans, Arial, sans-serif",
            fontSize: 46,
            lineHeight: 1.2,
            fontWeight: 500,
            fontStyle: st.italic ? "italic" : "normal",
            textAlign: "center",
            textWrap: "balance",
          }}
        >
          {page.words.map((w, i) => {
            const on = t >= w.s - 0.03;
            return (
              <span
                key={i}
                style={{
                  color: on ? st.color : "rgba(255,250,240,0.45)",
                }}
              >
                {(i ? " " : "") + w.t}
              </span>
            );
          })}
        </span>
      </div>
    </div>
  );
};

/** Per-frame music gain: ducks under every spoken line (absolute film time). */
export const buildMusicGain = (fps: number, total: number) => {
  const spans = Object.values(LINES).map((l) => {
    const base = SCENES.find((s) => s.id === l.scene)!.start;
    return {
      s: base + l.at,
      e: base + l.at + l.duration,
      depth: l.speaker === "narrator" ? 0.42 : 0.30,
    };
  });
  const gains = new Float32Array(total);
  for (let f = 0; f < total; f++) {
    const t = f / fps;
    let g = 1;
    for (const sp of spans) {
      const attack = 0.18,
        release = 0.45;
      let k = 0;
      if (t >= sp.s - attack && t < sp.s) k = (t - (sp.s - attack)) / attack;
      else if (t >= sp.s && t <= sp.e) k = 1;
      else if (t > sp.e && t < sp.e + release) k = 1 - (t - sp.e) / release;
      g = Math.min(g, 1 - k * (1 - sp.depth));
    }
    const fadeIn = Math.min(1, f / 6);
    gains[f] = g * fadeIn;
  }
  return gains;
};
