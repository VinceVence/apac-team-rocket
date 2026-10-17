import React from "react";
import { CanvasImage, interpolate, staticFile } from "remotion";
import { Town } from "./World";
import { StoryFrame, C } from "./Visuals";
import { SceneCaptions, SceneVoice } from "./Voice";
import { clamp, Dip, Grain, ramp, useT } from "./Kit";

export const Cold: React.FC = () => {
  const t = useT();
  return (
    <>
      <StoryFrame label="Illustrated phishing story">
        <Town
          time={t}
          zoom={interpolate(t, [0, 7], [1.04, 1.12], clamp)}
          cx={480}
          cy={315}
          dark={0.16}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "linear-gradient(120deg,#123622c0,transparent 65%), radial-gradient(ellipse at 90% 5%,#ffe7a260,transparent 60%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 115,
            top: 245,
            opacity: ramp(t, 0.3, 1.2),
            transform: "translateY(" + (1 - ramp(t, 0.3, 1.2)) * 25 + "px)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
            <CanvasImage
              src={staticFile("mark.svg")}
              style={{ width: 76, height: 76 }}
            />
            <span
              style={{
                fontSize: 30,
                letterSpacing: 5,
                fontWeight: 600,
                color: C.mint,
              }}
            >
              09:02 AM
            </span>
          </div>
          <div
            style={{
              fontSize: 158,
              lineHeight: 1.05,
              letterSpacing: -7,
              fontWeight: 700,
              marginTop: 20,
            }}
          >
            Mint Town.
          </div>
          <div style={{ fontSize: 48, marginTop: 22, color: "#f8e9b6" }}>
            An ordinary morning.
          </div>
        </div>
        <Dip duration={7} inFor={0.8} />
      </StoryFrame>
      <Grain />
      <SceneCaptions scene="cold" />
      <SceneVoice scene="cold" />
    </>
  );
};
