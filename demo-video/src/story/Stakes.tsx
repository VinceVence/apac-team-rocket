import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { Town } from "./World";
import { StoryFrame, Icon, C } from "./Visuals";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { clamp, Grain, pop, ramp, useShake, useT } from "./Kit";
import { LINES, word } from "./script";

/** Music drops to silence here (see tools/score_v2.py: 72.4s absolute). */
const CUT = 19.4;

/** One customer's story opens into the wider financial-services problem. */
export const Stakes: React.FC = () => {
  const t = useT();
  const p96 = word("stakes_1", "ninety-six") - 0.05;
  const p45 = word("stakes_2", "Forty-five") - 0.05;
  const p48 = word("stakes_3", "two") - 0.05;
  const phase = t < p96 ? -1 : t < p45 ? 0 : t < p48 ? 1 : 2;
  const hitAt = [p96, p45, p48][Math.max(0, phase)];
  const shake = useShake([p96, p45, p48], 9, 8);
  const nums = ["96%", "45%", "2–7 days"];
  const subs = [
    "worried about scams or hacking",
    "of reported scam cases unresolved",
    "to investigate unauthorized transactions",
  ];
  const notes = [
    "3,000 adults · 6 ASEAN markets · self-reported",
    "Among cases reported to an organization",
    "GCash guidance · not an industry average",
  ];
  const sources = [
    "GSMA / Armidale · ASEAN Consumer Scam Report 2026",
    "GSMA / Armidale · ASEAN Consumer Scam Report 2026",
    "GCash Help Center · 17 Oct 2026",
  ];
  const pivot = t >= CUT;
  const pivotWords = LINES.stakes_pivot.words;
  return (
    <>
      <StoryFrame brand="town" label="External research">
        <AbsoluteFill style={{ transform: shake }}>
          <Town
            time={46 + t / 3}
            zoom={interpolate(t, [0, 6], [2.0, 1.0], clamp)}
            cx={interpolate(t, [0, 6], [710, 480], clamp)}
            cy={interpolate(t, [0, 6], [470, 300], clamp)}
            mode="panic"
            dark={interpolate(t, [0, 3, p96], [0.55, 0.7, 0.86], clamp)}
            filter="grayscale(0.7)"
          />
          {phase === -1 && (
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: 380,
                textAlign: "center",
                fontSize: 100,
                fontWeight: 700,
                letterSpacing: -3,
                opacity: ramp(t, 0.5, 1.2) * (1 - ramp(t, p96 - 0.5, p96 - 0.1)),
                textShadow: "0 6px 30px #020b08",
              }}
            >
              One story among many.
              <div style={{ fontSize: 36, letterSpacing: 0, color: C.mint, marginTop: 26 }}>
                Across financial services
              </div>
            </div>
          )}
          {phase >= 0 && !pivot && (
            <>
              {/* 100-person grid */}
              <div
                style={{
                  position: "absolute",
                  right: 70,
                  top: 150,
                  width: 900,
                  height: 760,
                  transform: "perspective(1400px) rotateY(-14deg)",
                  opacity: 0.9,
                }}
              >
                {phase < 2
                  ? Array.from({ length: 100 }, (_, i) => {
                      const target = [96, 45][phase];
                      const fill = Math.floor(target * ramp(t, hitAt, hitAt + 1.4, false));
                      const on = i < fill;
                      const x = (i % 10) * 88,
                        y = Math.floor(i / 10) * 74;
                      return (
                        <div
                          key={i}
                          style={{
                            position: "absolute",
                            left: x,
                            top: y + Math.sin(t * 0.6 + i * 0.5) * 3,
                            color: on ? (phase === 0 ? "#ffd99a" : "#f2a07f") : "#4b6a5a",
                            transform: `scale(${on ? 1.05 : 0.9})`,
                          }}
                        >
                          <Icon kind="person" size={56} />
                        </div>
                      );
                    })
                  : (
                    <svg width="760" height="760" viewBox="0 0 800 800" style={{ marginLeft: 80 }}>
                      <rect x="80" y="130" width="640" height="570" rx="32" fill="#132f26" stroke="#668777" strokeWidth="4" />
                      <path d="M112 130H688Q720 130 720 162V255H80V162Q80 130 112 130" fill="#eacb96" />
                      <path d="M235 95V165M565 95V165" stroke="#f7f4df" strokeWidth="18" strokeLinecap="round" />
                      <text x="400" y="225" textAnchor="middle" fill="#254c38" fontSize="42" fontWeight="700" letterSpacing="6">DAY</text>
                      <text x="400" y="540" textAnchor="middle" fill="#fff9e9" fontSize="260" fontWeight="700">
                        {2 + Math.min(5, Math.floor(ramp(t, p48, CUT, false) * 6))}
                      </text>
                      {Array.from({length: 7}, (_, i) => (
                        <circle key={i} cx={190 + i * 70} cy="625" r="14"
                          fill={i >= 1 && i <= 1 + Math.floor(ramp(t,p48,CUT,false)*6) ? C.mint : "#3c594a"} />
                      ))}
                    </svg>
                  )}
              </div>
              {/* number */}
              <div style={{ position: "absolute", left: 100, top: 170, width: 900 }}>
                <div style={{ fontSize: 24, letterSpacing: 4, color: C.mint, fontWeight: 600 }}></div>
                <div
                  key={phase}
                  style={{
                    marginTop: 60,
                    fontSize: phase === 2 ? 128 : 230,
                    lineHeight: 1,
                    fontWeight: 700,
                    letterSpacing: -8,
                    transform: `scale(${pop(t, hitAt, 0.35)})`,
                    transformOrigin: "left bottom",
                    color: phase === 1 ? "#ffc3a8" : "#fff9e9",
                  }}
                >
                  {nums[phase]}
                </div>
                <div style={{ fontSize: 40, lineHeight: 1.25, marginTop: 26, width: 820, opacity: ramp(t, hitAt + 0.15, hitAt + 0.6) }}>
                  {subs[phase]}
                </div>
                <div style={{ fontSize: 22, color: "#bad1bd", lineHeight: 1.5, marginTop: 30, width: 820, opacity: ramp(t, hitAt + 0.4, hitAt + 0.9) }}>
                  {notes[phase]}
                </div>
              </div>
              <div style={{ position: "absolute", left: 100, bottom: 170, fontSize: 18, color: "#c3d0bd" }}>{sources[phase]}</div>
            </>
          )}
        </AbsoluteFill>
      </StoryFrame>
      {pivot && (
        <AbsoluteFill style={{ background: "#030c09", alignItems: "center", justifyContent: "center", fontFamily: "DM Sans, Arial, sans-serif" }}>
          <div style={{ width: 1500, textAlign: "center", fontSize: 92, fontWeight: 700, lineHeight: 1.12, letterSpacing: -2.5, color: "#fff9e9" }}>
            {pivotWords.map((w, i) => {
              const tail = i >= pivotWords.length - 6;
              const on = t >= w.s - 0.05;
              return (
                <span
                  key={i}
                  style={{
                    opacity: on ? 1 : 0.08,
                    color: tail ? C.mint : undefined,
                    textShadow: tail && on ? "0 0 40px #8ef0b866" : undefined,
                  }}
                >
                  {(i ? " " : "") + w.t}
                </span>
              );
            })}
          </div>
        </AbsoluteFill>
      )}
      <Grain amount={0.09} />
      {!pivot && <SceneCaptions scene="stakes" />}
      <SceneVoice scene="stakes" />
      <Sfx name="impact" at={p96} volume={0.5} />
      <Sfx name="impact" at={p45} volume={0.5} />
      <Sfx name="impact" at={p48} volume={0.5} />
    </>
  );
};
