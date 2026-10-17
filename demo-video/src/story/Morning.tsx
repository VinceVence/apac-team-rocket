import React from "react";
import { interpolate } from "remotion";
import { Town, Portrait } from "./World";
import { StoryFrame, C, Icon } from "./Visuals";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { clamp, Dip, Grain, ramp, useT } from "./Kit";
import { word } from "./script";

export const Morning: React.FC = () => {
  const t = useT(),
    coffee = word("morning_1", "Coffee"),
    groceries = word("morning_1", "Groceries");
  const wallet = word("morning_1", "checks"),
    message = word("morning_1", "message");
  const zoom = interpolate(
    t,
    [0, 3, 7, 12, 17, 22],
    [1.04, 1.1, 1.15, 1.25, 1.32, 1.32],
    clamp,
  );
  const cx = interpolate(
    t,
    [0, 3, 7, 12, 17, 22],
    [480, 480, 380, 500, 600 + 440 / 2.64, 600 + 440 / 2.64],
    clamp,
  );
  const cy = interpolate(
    t,
    [0, 3, 7, 12, 17, 22],
    [315, 320, 390, 440, 470, 470],
    clamp,
  );
  const x = interpolate(
    t,
    [0, 3, 4.5, 6, 8, 10, 15, 22],
    [150, 150, 315, 315, 150, 315, 600, 600],
    clamp,
  );
  const y = interpolate(
    t,
    [0, 3, 4.5, 6, 8, 10, 15, 22],
    [260, 260, 260, 485, 485, 485, 485, 485],
    clamp,
  );
  return (
    <>
      <StoryFrame brand="town" label="Ana's morning">
        <Town
          time={t}
          zoom={zoom}
          cx={cx}
          cy={cy}
          anaPosition={{ x, y, direction: t > 4.5 && t < 6 ? "down" : "right" }}
          tags={{ C001: "Ana" }}
          dark={0.05}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "linear-gradient(130deg,#ffe6a42b,transparent 65%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 100,
            top: 135,
            opacity: ramp(t, 0.15, 0.7) * (1 - ramp(t, 3.8, 4.6)),
            textShadow: "0 3px 26px #102e23",
          }}
        >
          <div style={{ fontSize: 24, letterSpacing: 4, color: C.lime }}>
            A MORNING IN MINT TOWN
          </div>
          <div
            style={{
              fontSize: 104,
              fontWeight: 700,
              letterSpacing: -4,
              marginTop: 16,
            }}
          >
            Meet Ana.
          </div>
        </div>
        <div
          style={{
            position: "absolute",
            right: 100,
            top: 210,
            width: 510,
            padding: 34,
            boxSizing: "border-box",
            borderRadius: 30,
            background: "#f8f8eaef",
            color: C.ink,
            boxShadow: "0 25px 65px #14352255",
            opacity:
              ramp(t, 0.7, 1.4) * (1 - ramp(t, message - 1, message - 0.3)),
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <Portrait size={125} />
            <div>
              <div style={{ fontSize: 46, fontWeight: 700 }}>Ana</div>
              <div style={{ fontSize: 24, color: "#6a806c", marginTop: 8 }}>
                Resident 1
              </div>
            </div>
          </div>
          {[
            [coffee, "Coffee before work", "₱65"],
            [groceries, "Groceries for home", "₱120"],
          ].map(([on, label, amount]) => (
            <div
              key={String(label)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                borderTop: "1px solid #d9e2cd",
                paddingTop: 20,
                marginTop: 20,
                fontSize: 25,
                opacity: ramp(t, Number(on), Number(on) + 0.3),
              }}
            >
              <span>{label}</span>
              <b style={{ color: C.green }}>{amount} ✓</b>
            </div>
          ))}
          <div
            style={{
              marginTop: 26,
              background: "#e3edce",
              borderRadius: 18,
              padding: 22,
              fontSize: 27,
              lineHeight: 1.35,
              opacity: ramp(t, wallet, wallet + 0.4),
            }}
          >
            The rest is her
            <br />
            <b>budget for the week.</b>
          </div>
        </div>
        <div
          style={{
            position: "absolute",
            right: 100,
            top: 270,
            width: 570,
            padding: 34,
            boxSizing: "border-box",
            borderRadius: 28,
            background: "#f8f8eafa",
            color: C.ink,
            boxShadow: "0 25px 65px #14352255",
            opacity: ramp(t, message - 0.2, message + 0.4),
            transform:
              "translateY(" +
              (1 - ramp(t, message - 0.2, message + 0.4)) * 30 +
              "px)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 18,
              fontSize: 24,
              color: "#687b67",
            }}
          >
            <Icon kind="alert" size={36} />
            NEW MESSAGE
          </div>
          <div style={{ fontSize: 38, fontWeight: 700, marginTop: 18 }}>
            Your wallet is at risk.
          </div>
          <div style={{ fontSize: 25, marginTop: 14, color: "#916d49" }}>
            A familiar name. An urgent warning.
          </div>
        </div>
        <Dip duration={17.5} inFor={0.5} />
      </StoryFrame>
      <Grain />
      <SceneCaptions scene="morning" />
      <SceneVoice scene="morning" />
      <Sfx name="coin" at={coffee} volume={0.22} />
      <Sfx name="coin" at={groceries} volume={0.22} />
      <Sfx name="blip" at={message} volume={0.32} />
    </>
  );
};
