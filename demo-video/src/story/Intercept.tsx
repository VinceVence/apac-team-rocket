import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { Town } from "./World";
import { StoryFrame, C, Icon } from "./Visuals";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { PhishingPhone } from "./PhishingPhone";
import { clamp, Dread, Flash, Grain, Highlight, pop, ramp, useShake, useT } from "./Kit";
import { at, word } from "./script";

const HOLD = 14.5;
export const Intercept: React.FC = () => {
  const t = useT(),
    safe = word("repeat_2", "safe"),
    secret = word("repeat_2", "secret"),
    coffee = word("repeat_4", "coffee");
  const held = t >= HOLD,
    zoom = interpolate(
      t,
      [0, 5, 14, 15, 22],
      [1.25, 1.7, 1.95, 1.7, 1.35],
      clamp,
    );
  const match = [t >= safe, t >= secret],
    shake = useShake([HOLD], 18, 6);
  return (
    <>
      <StoryFrame label="Protection before payment">
        <AbsoluteFill style={{ transform: shake }}>
          <Town
            time={148 + t}
            zoom={zoom}
            cx={315 + 320 / (2 * zoom)}
            cy={310 + 210 / (2 * zoom)}
            mode={held ? "protect" : "day"}
            quiet
            tags={{ C002: "Jun" }}
            dark={held ? 0.05 : interpolate(t, [3, 14], [0.05, 0.35], clamp)}
          />
          <Dread
            intensity={ramp(t, 5, HOLD, false) * (held ? 0 : 1)}
            bpm={94}
          />
          <div
            style={{
              position: "absolute",
              left: 100,
              top: 130,
              opacity: ramp(t, 0.1, 0.8) * (1 - ramp(t, 4.7, 5.2)),
              textShadow: "0 4px 22px #092818",
            }}
          >
            <div style={{ fontSize: 26, letterSpacing: 4, color: C.lime }}>
              LATER THAT DAY
            </div>
            <div
              style={{
                fontSize: 82,
                fontWeight: 700,
                lineHeight: 1.05,
                letterSpacing: -3,
                marginTop: 15,
              }}
            >
              New link.
              <br />
              Different resident.
            </div>
          </div>
          {!held && t >= 5.5 && (
            <div
              style={{
                position: "absolute",
                left: 100,
                top: 510,
                width: 620,
                boxSizing: "border-box",
                padding: 32,
                borderRadius: 26,
                background: "#0c2a20eb",
                border: "2px solid #86b394",
                opacity: ramp(t, 5.5, 6),
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 18,
                  alignItems: "center",
                  fontSize: 25,
                  fontWeight: 700,
                  color: C.mint,
                }}
              >
                <Icon kind="shield" size={45} />
                PREVENTION AGENT
              </div>
              {["“Safe account”", "“Keep it secret”"].map((v, i) => (
                <div
                  key={v}
                  style={{
                    display: "flex",
                    gap: 18,
                    alignItems: "center",
                    fontSize: 35,
                    marginTop: 20,
                    color: match[i] ? C.lime : "#839e8d",
                  }}
                >
                  <Icon kind={match[i] ? "check" : "alert"} size={32} />
                  {v}
                </div>
              ))}
              <div style={{ fontSize: 24, color: "#d4e8c7", marginTop: 24 }}>
                {match[1]
                  ? "Approved pattern matched"
                  : "Checking the payment request…"}
              </div>
            </div>
          )}
          {held && (
            <>
              <AbsoluteFill
                style={{
                  background:
                    "linear-gradient(90deg,#092617c9,transparent 58%)",
                  opacity: ramp(t, HOLD, HOLD + 0.5),
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: 100,
                  top: 460,
                  transform: "scale(" + pop(t, HOLD, 0.4) + ")",
                  transformOrigin: "left top",
                  textShadow: "0 5px 24px #062116",
                }}
              >
                <div style={{ fontSize: 27, letterSpacing: 4, color: C.mint }}>
                  PREVENTION AGENT
                </div>
                <div
                  style={{
                    fontSize: 108,
                    fontWeight: 800,
                    letterSpacing: -4,
                    lineHeight: 0.98,
                    marginTop: 15,
                  }}
                >
                  Stopped
                  <br />
                  before debit.
                </div>
                <div style={{ fontSize: 28, marginTop: 26, color: "#d9eed2" }}>
                  A new recipient. The same pattern.
                </div>
              </div>
              {t >= coffee && (
                <div
                  style={{
                    position: "absolute",
                    left: 100,
                    top: 800,
                    display: "flex",
                    gap: 20,
                    alignItems: "center",
                    background: "#f7f7e5",
                    color: C.ink,
                    padding: "20px 28px",
                    borderRadius: 20,
                    fontSize: 31,
                    fontWeight: 600,
                    transform: "scale(" + pop(t, coffee) + ")",
                    transformOrigin: "left",
                  }}
                >
                  <Icon kind="check" size={40} />
                  Coffee payment · approved
                </div>
              )}
            </>
          )}
          <PhishingPhone
            pageAt={4.8}
            requestAt={at("repeat_2")}
            transferAt={12.4}
            resultAt={HOLD}
            recipient="Recipient B"
            protectedPayment
          />
          <Highlight at={safe} x={112} y={600} width={590} height={55} />
          <Highlight at={secret} x={112} y={665} width={590} height={55} />
          <Highlight at={coffee} x={100} y={800} width={530} height={80} />
        </AbsoluteFill>
        <Flash at={HOLD} peak={0.65} len={0.5} color="#f0ffea" />
      </StoryFrame>
      <Grain />
      <SceneCaptions scene="intercept" />
      <SceneVoice scene="intercept" />
      <Sfx name="blip" at={0.4} volume={0.35} />
      <Sfx name="blip" at={safe} volume={0.3} />
      <Sfx name="blip" at={secret} volume={0.3} rate={1.3} />
      <Sfx name="shield" at={HOLD} volume={0.65} />
      <Sfx name="check" at={HOLD + 0.08} volume={0.44} rate={0.85} />
      <Sfx name="coin" at={coffee} volume={0.44} />
    </>
  );
};
