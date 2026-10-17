import React from "react";
import { interpolate } from "remotion";
import { Portrait, Town } from "./World";
import { StoryFrame, C } from "./Visuals";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { clamp, Grain, pop, ramp, typed, useT } from "./Kit";
import { word } from "./script";

const STORY =
  "I followed a text to a page that looked like my wallet. I sent ₱900. Now I can't reach anyone.";

/** Illustrated phishing complaint. The backend chapter separately identifies the recorded case. */
export const After: React.FC = () => {
  const t = useT();
  const L = "after_1";
  const reportAt = word(L, "files") - 0.1;
  const filedAt = word(L, "then");
  const waitAt = word(L, "Days");
  const formOn = t >= reportAt;
  const dayLength = (10.5 - waitAt) / 3;
  const day = Math.max(1, Math.min(3, 1 + Math.floor((t - waitAt) / dayLength)));
  const dayAt = waitAt + (day - 1) * dayLength;
  return (
    <>
      <StoryFrame brand="town" label="Illustrated story">
        <Town
          time={35 + t}
          zoom={2.0}
          cx={710}
          cy={470}
          mode="panic"
          dark={interpolate(t, [0, 11], [0.35, 0.6], clamp)}
          filter={`grayscale(${interpolate(t, [0, 4], [0.4, 0.75], clamp)})`}
        />
        <div style={{ position: "absolute", left: 205, top: 155, width: 650, height: 690,
          opacity: 1 - ramp(t, waitAt - 0.25, waitAt + 0.1),
          transform: `translateX(${Math.sin(t * 36) * 10 * Math.exp(-t * 0.7)}px)` }}>
          <div style={{ position: "absolute", inset: 0,
            background: "radial-gradient(ellipse, #f69e7955, transparent 68%)" }} />
          <svg width="650" height="690" style={{ position: "absolute", inset: 0 }}>
            {[[115, 150, 170, 210], [75, 290, 155, 310], [485, 150, 440, 215], [535, 290, 465, 315]].map(([x1,y1,x2,y2],i) => (
              <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#ffe6bd" strokeWidth="9"
                strokeLinecap="round" opacity={0.55 + 0.45 * Math.abs(Math.sin(t * 8 + i))} />
            ))}
          </svg>
          <div style={{ position: "absolute", left: 105, top: 140 }}>
            <Portrait size={440} upset closeup />
          </div>
          <div style={{ position: "absolute", right: 60, top: 40, color: "#ffe6bd",
            fontSize: 150, fontWeight: 800, rotate: "8deg", scale: pop(t, 0.06),
            textShadow: "0 8px 30px #572318" }}>!</div>
        </div>
        <div
          style={{
            position: "absolute",
            left: 1170,
            top: 120,
            width: 580,
            height: 820,
            borderRadius: 52,
            background: "#f7f8ef",
            color: C.ink,
            border: "13px solid #5a2c24",
            boxShadow: "0 30px 110px #02100b99",
            padding: "70px 38px 0",
            fontFamily: "DM Sans, Arial, sans-serif",
          }}
        >
          {!formOn ? (
            <>
              <div
                style={{
                  fontSize: 19,
                  letterSpacing: 3,
                  color: "#a0563f",
                  fontWeight: 700,
                }}
              >
                CONNECTION LOST
              </div>
              <div style={{ fontSize: 40, fontWeight: 700, marginTop: 18 }}>
                Page unavailable.
              </div>
              <div
                style={{
                  fontSize: 26,
                  color: "#9a6a55",
                  marginTop: 26,
                  lineHeight: 1.5,
                }}
              >
                Trying to reconnect…
                <br />
                <span style={{ opacity: t > 1.8 ? 1 : 0 }}>No response.</span>
              </div>
            </>
          ) : (
            <>
              <div
                style={{
                  fontSize: 19,
                  letterSpacing: 3,
                  color: "#46705a",
                  fontWeight: 700,
                }}
              >
                REPORT A SCAM
              </div>
              <div style={{ fontSize: 22, color: "#7d8b77", marginTop: 14 }}>
                Ana · Resident 1
              </div>
              <div
                style={{
                  fontSize: 30,
                  lineHeight: 1.45,
                  marginTop: 24,
                  minHeight: 280,
                }}
              >
                “{typed(STORY, t, reportAt + 0.1, filedAt - 0.1)}”
              </div>
              {t >= filedAt && (
                <div
                  style={{
                    marginTop: 16,
                    background: "#dcefdc",
                    padding: "16px 20px",
                    borderRadius: 12,
                    fontSize: 25,
                    color: "#245e42",
                    fontWeight: 600,
                    transform: `scale(${pop(t, filedAt)})`,
                    transformOrigin: "left",
                  }}
                >
                  Report filed
                </div>
              )}
              {t >= waitAt && (
                <div
                  style={{
                    marginTop: 22,
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                    fontSize: 27,
                    color: "#9a5d42",
                  }}
                >
                  <div
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: 20,
                      border: "4px solid #e6c9b6",
                      borderTopColor: "#9a5d42",
                      transform: `rotate(${t * 400}deg)`,
                    }}
                  />
                  Waiting for an update…
                </div>
              )}
            </>
          )}
        </div>
        {t >= waitAt - 0.2 && (
          <div
            style={{
              position: "absolute",
              left: 120,
              top: 170,
              opacity: ramp(t, waitAt - 0.2, waitAt + 0.5),
              textShadow: "0 4px 18px #04140f",
            }}
          >
            <div style={{ fontSize: 76, fontWeight: 700, letterSpacing: -2 }}>Days can pass.</div>
            <div style={{ position: "relative", marginLeft: 140, marginTop: 60, width: 390, height: 395,
              background: "#fff7e7", color: C.ink, borderRadius: 24, overflow: "hidden",
              boxShadow: "0 25px 80px #06191288", textAlign: "center", textShadow: "none" }}>
              <div style={{ background: "#a2543e", color: "#fff7e7", padding: 24,
                fontSize: 27, fontWeight: 700, letterSpacing: 5 }}>DAY</div>
              <div key={day} style={{ fontSize: 180, fontWeight: 700, lineHeight: 1.2,
                fontVariantNumeric: "tabular-nums", transform: `translateY(${(1-ramp(t,dayAt,dayAt+0.22))*-30}px)`,
                opacity: ramp(t, dayAt, dayAt + 0.15) }}>{day}</div>
              <div style={{ fontSize: 27, color: "#9a5d42", marginTop: 10 }}>Still unresolved</div>
            </div>
          </div>
        )}
      </StoryFrame>
      <Grain amount={0.09} />
      <SceneCaptions scene="after" />
      <SceneVoice scene="after" />
      <Sfx name="ding_sour" at={0.1} volume={0.25} />
      <Sfx name="typing" at={reportAt + 0.1} volume={0.45} />
      <Sfx name="check" at={filedAt} volume={0.4} />
      {[0,1,2].map(i => <Sfx key={i} name="stamp" at={waitAt + i * dayLength} volume={0.23} rate={1.1} />)}
    </>
  );
};
