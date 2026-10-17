import React from "react";
import { AbsoluteFill } from "remotion";
import { StoryFrame, C, Icon, Paper } from "./Visuals";
import { ModelToolFlow } from "./EvidenceGraphics";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { Grain, Highlight, ramp, pop, useT } from "./Kit";
import { at } from "./script";

export const Model: React.FC = () => {
  const t = useT(),
    result = at("model_3"),
    draft = at("model_4");
  return (
    <>
      <StoryFrame label="Models as tools">
        <ModelToolFlow time={t * 0.4} />
        {t >= 4.8 && t < result && (
          <div
            style={{
              position: "absolute",
              left: 650,
              top: 800,
              width: 620,
              textAlign: "center",
              fontSize: 29,
              color: C.mint,
              opacity: ramp(t, 4.8, 5.3),
            }}
          >
            Trained models · classifiers · risk checks
          </div>
        )}
        {t >= result && (
          <AbsoluteFill
            style={{
              background:
                "radial-gradient(ellipse at center,#214a37,#092218 75%)",
              opacity: ramp(t, result, result + 0.4),
            }}
          >
            <div
              style={{
                position: "absolute",
                left: 130,
                top: 170,
                fontSize: 68,
                fontWeight: 700,
                letterSpacing: -2,
              }}
            >
              Model results become useful evidence.
            </div>
            <div
              style={{
                position: "absolute",
                left: 150,
                top: 330,
                width: 700,
                transform: "scale(" + pop(t, result + 0.2) + ")",
              }}
            >
              <Paper rotate={-2} style={{ padding: 48 }}>
                <Icon kind="model" size={80} />
                <div style={{ fontSize: 48, fontWeight: 700, marginTop: 25 }}>
                  Classifier check complete
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 16,
                    alignItems: "center",
                    fontSize: 30,
                    color: C.green,
                    marginTop: 28,
                  }}
                >
                  <Icon kind="check" size={34} />
                  Result returned to the agent
                </div>
                <div style={{ fontSize: 27, marginTop: 28, color: "#667f67" }}>
                  One part of the case.
                </div>
              </Paper>
            </div>
            <svg
              width="1920"
              height="1080"
              style={{
                position: "absolute",
                inset: 0,
                opacity: ramp(t, draft, draft + 0.5),
              }}
            >
              <path
                d="M900 550 H1070m-20-12 20 12-20 12"
                stroke={C.mint}
                strokeWidth="4"
                fill="none"
              />
            </svg>
            <div
              style={{
                position: "absolute",
                left: 1120,
                top: 350,
                width: 650,
                opacity: ramp(t, draft, draft + 0.5),
                transform:
                  "translateY(" +
                  (1 - ramp(t, draft, draft + 0.5)) * 35 +
                  "px)",
              }}
            >
              <Paper rotate={2} style={{ padding: 44 }}>
                <div style={{ fontSize: 24, color: C.green, letterSpacing: 2 }}>
                  ANALYST-READY SUMMARY
                </div>
                <div style={{ fontSize: 46, fontWeight: 700, marginTop: 20 }}>
                  Evidence, brought together.
                </div>
                <div style={{ fontSize: 29, lineHeight: 1.5, marginTop: 24 }}>
                  Customer report
                  <br />
                  Transaction history
                  <br />
                  Model findings
                </div>
              </Paper>
            </div>
          </AbsoluteFill>
        )}
        <Highlight at={3.1} x={1340} y={410} width={260} height={260} />
        <Highlight at={result + 0.22} x={145} y={330} width={710} height={390} />
        <Highlight at={draft + 0.2} x={1115} y={350} width={660} height={375} />
      </StoryFrame>
      <Grain />
      <SceneCaptions scene="model" />
      <SceneVoice scene="model" />
      <Sfx name="scan" at={0.4} volume={0.28} />
      <Sfx name="blip" at={3.1} volume={0.4} />
      <Sfx name="check" at={result} volume={0.46} />
      <Sfx name="blip" at={draft} volume={0.38} />
    </>
  );
};
