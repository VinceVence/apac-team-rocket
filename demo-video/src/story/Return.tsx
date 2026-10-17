import React from "react";
import { interpolate } from "remotion";
import { Town } from "./World";
import { StoryFrame, Icon, C } from "./Visuals";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { clamp, Dip, Grain, Highlight, ramp, useT } from "./Kit";
import { word } from "./script";

export const Return: React.FC = () => {
  const t = useT();
  const close = word("return_1", "Close");
  const resolution = word("return_1", "resolution", 1);
  return (
    <>
      <StoryFrame label="Fraud analyst assistance">
        <Town
          time={170 + t}
          zoom={interpolate(t, [0, 10], [1.25, 1], clamp)}
          mode="calm"
          dark={0.76}
          quiet
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(ellipse at center,#23503c60,transparent 80%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 180,
            textAlign: "center",
            opacity: ramp(t, 0.1, 0.8),
            transform: "translateY(" + (1 - ramp(t, 0.1, 0.8)) * 25 + "px)",
          }}
        >
          <div
            style={{
              display: "grid",
              placeItems: "center",
              width: 135,
              height: 135,
              margin: "0 auto",
              borderRadius: 40,
              background: C.mint,
              color: C.ink,
            }}
          >
            <Icon size={94} />
          </div>
          <div
            style={{
              fontSize: 132,
              fontWeight: 700,
              letterSpacing: -5,
              marginTop: 26,
            }}
          >
            Resolution Agent
          </div>
          <div
            style={{
              fontSize: 52,
              lineHeight: 1.35,
              color: C.mint,
              marginTop: 20,
            }}
          >
            Close the gap.
            <br />
            From report to resolution.
          </div>
          <div style={{ height: 4, width: 660 * ramp(t, close, resolution + 0.2),
            margin: "24px auto 0", borderRadius: 4,
            background: "linear-gradient(90deg, transparent, " + C.mint + ", transparent)" }} />
          <div style={{ fontSize: 22, color: "#bdcfb5", marginTop: 38 }}>
            Team Rocket · AI Builder Cup BFSI
          </div>
          <div style={{ fontSize: 18, color: "#b4c8ad", marginTop: 20 }}>
            Illustrated story · recorded tool evidence · synthetic voices
          </div>
        </div>
        <Highlight at={0.45} x={892} y={180} width={135} height={135} />
        <Dip duration={10} outFor={0.8} />
      </StoryFrame>
      <Grain />
      <SceneCaptions scene="return" />
      <SceneVoice scene="return" />
      <Sfx name="check" at={0.45} volume={0.34} rate={0.9} />
      <Sfx name="ding" at={resolution} volume={0.28} />
    </>
  );
};
