import React from "react";
import { StoryFrame, C, Icon, Paper } from "./Visuals";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { Grain, Highlight, ramp, pop, useT } from "./Kit";
import { at, word } from "./script";

export const Lesson: React.FC = () => {
  const t = useT(),
    knowledge = word("lesson_1", "knowledge"),
    pattern = at("lesson_2"),
    checks = at("lesson_3");
  return (
    <>
      <StoryFrame label="Learning from reviewed cases">
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(ellipse at center,#224c38,#092218 75%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 130,
            top: 145,
            fontSize: 74,
            fontWeight: 700,
            letterSpacing: -3,
          }}
        >
          Reviewed cases. Smarter protection.
        </div>
        <div
          style={{
            position: "absolute",
            left: 160,
            top: 340,
            width: 650,
            transform: "scale(" + pop(t, 0.2) + ")",
          }}
        >
          <Paper rotate={-2} style={{ padding: 42 }}>
            <Icon kind="book" size={76} />
            <div style={{ fontSize: 46, fontWeight: 700, marginTop: 22 }}>
              Shared knowledge
            </div>
            <div style={{ fontSize: 28, color: "#637e66", marginTop: 20 }}>
              Patterns from reviewed cases
            </div>
            <div
              style={{
                fontSize: 31,
                lineHeight: 1.6,
                marginTop: 30,
                opacity: ramp(t, pattern, pattern + 0.6),
              }}
            >
              “Safe account”
              <br />
              “Keep it secret”
            </div>
          </Paper>
        </div>
        <svg
          width="1920"
          height="1080"
          style={{
            position: "absolute",
            inset: 0,
            opacity: ramp(t, knowledge, knowledge + 0.5),
          }}
        >
          <path
            d="M870 550 H1130m-20-12 20 12-20 12"
            stroke={C.mint}
            strokeWidth="4"
            fill="none"
          />
          <circle
            cx={870 + 260 * ramp(t, knowledge, knowledge + 1.3)}
            cy="550"
            r="12"
            fill={C.lime}
          />
        </svg>
        <div
          style={{
            position: "absolute",
            left: 1190,
            top: 330,
            width: 540,
            textAlign: "center",
            opacity: ramp(t, knowledge, knowledge + 0.5),
          }}
        >
          <div
            style={{
              width: 220,
              height: 220,
              borderRadius: 70,
              display: "grid",
              placeItems: "center",
              background: C.mint,
              color: C.ink,
              margin: "0 auto",
            }}
          >
            <Icon kind="shield" size={135} />
          </div>
          <div style={{ fontSize: 43, fontWeight: 700, marginTop: 28 }}>
            Prevention agent
          </div>
          <div style={{ fontSize: 29, color: "#c7ddc3", marginTop: 16 }}>
            Recognizes related requests
          </div>
        </div>
        <div
          style={{
            position: "absolute",
            left: 160,
            right: 160,
            top: 840,
            display: "flex",
            gap: 26,
            opacity: ramp(t, checks, checks + 0.5),
          }}
        >
          {["New recipients", "Similar requests", "Ordinary payments"].map(
            (s, i) => (
              <div
                key={s}
                style={{
                  flex: 1,
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  gap: 16,
                  borderRadius: 18,
                  padding: 22,
                  background: i === 2 ? "#dfeccc" : "#254b38",
                  color: i === 2 ? C.ink : "#e6f0d9",
                  fontSize: 28,
                }}
              >
                <Icon kind={i === 2 ? "check" : "shield"} size={35} />
                {s}
              </div>
            ),
          )}
        </div>
        <Highlight at={knowledge + 1.3} x={1350} y={330} width={220} height={220} />
      </StoryFrame>
      <Grain />
      <SceneCaptions scene="lesson" />
      <SceneVoice scene="lesson" />
      <Sfx name="scan" at={knowledge} volume={0.28} />
      <Sfx name="check" at={knowledge + 1.3} volume={0.4} />
      <Sfx name="shield" at={pattern} volume={0.35} />
      <Sfx name="check" at={checks} volume={0.3} />
    </>
  );
};
