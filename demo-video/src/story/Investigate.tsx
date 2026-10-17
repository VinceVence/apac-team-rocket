import React from "react";
import { AbsoluteFill } from "remotion";
import { Portrait } from "./World";
import { StoryFrame, Icon, C, Paper } from "./Visuals";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { Flash, Grain, pop, ramp, useT } from "./Kit";
import { at, end, word } from "./script";
import { EvidenceReceipt } from "./EvidenceGraphics";

const ORB = { x: 1010, y: 470 };
const CARDS = [
  {
    key: "report",
    text: "Customer report",
    sub: "A claim to verify",
    x: 1370,
    y: 190,
    icon: "book",
  },
  {
    key: "transfer",
    text: "₱900 transfer",
    sub: "Verified transfer",
    x: 1390,
    y: 470,
    icon: "data",
  },
  {
    key: "history",
    text: "Wallet history",
    sub: "Before the report",
    x: 1350,
    y: 740,
    icon: "data",
  },
];

/** 1:17 Act II. The resolution agent listens, connects, and makes its first real move. */
export const Investigate: React.FC = () => {
  const t = useT();
  const reveal = word("investigate_1", "Resolution");
  const listen = at("investigate_customer");
  const settle = ramp(t, listen - 0.7, listen + 0.15);
  const orbX = 960 + (ORB.x - 960) * settle;
  const orbY = 340 + (ORB.y - 340) * settle;
  const cardAt = [
    word("investigate_2", "report"),
    word("investigate_2", "transactions"),
    word("investigate_2", "history"),
  ];
  const dots = word("investigate_2", "case");
  const rec = at("investigate_3") - 0.25;
  const tool = word("investigate_3", "evidence");
  const footage = ramp(t, rec, rec + 0.5);
  const orbP = pop(t, Math.max(0, reveal - 0.18), 0.6) * (1.22 - 0.22 * settle);
  return (
    <>
      <StoryFrame
        label={t < rec ? "Fraud analyst assistance" : "Connected evidence"}
      >
        <AbsoluteFill
          style={{
            background:
              "radial-gradient(circle at 52% 45%, #1d4a39 0%, #0b241b 60%, #061611 100%)",
          }}
        />
        <svg
          width="1920"
          height="1080"
          style={{ position: "absolute", inset: 0, opacity: 0.18 }}
        >
          {Array.from({ length: 33 }, (_, i) => (
            <line
              key={`v${i}`}
              x1={i * 60}
              y1={0}
              x2={i * 60}
              y2={1080}
              stroke="#8fd3ad"
              strokeWidth={1}
            />
          ))}
          {Array.from({ length: 19 }, (_, i) => (
            <line
              key={`h${i}`}
              x1={0}
              y1={i * 60}
              x2={1920}
              y2={i * 60}
              stroke="#8fd3ad"
              strokeWidth={1}
            />
          ))}
        </svg>
        <svg
          width="1920"
          height="1080"
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            opacity:
              ramp(t, reveal - 0.2, reveal + 0.1) *
              (1 - ramp(t, reveal + 0.6, listen)),
          }}
        >
          <circle
            cx="960"
            cy="340"
            r={140 + 470 * ramp(t, reveal, reveal + 1.3)}
            fill="none"
            stroke={C.mint}
            strokeWidth="3"
            opacity="0.45"
          />
          <circle
            cx="960"
            cy="340"
            r={110 + 340 * ramp(t, reveal + 0.1, reveal + 1.1)}
            fill="none"
            stroke={C.lime}
            strokeWidth="2"
            opacity="0.3"
          />
          {[
            [715, 190],
            [1210, 220],
            [730, 470],
            [1230, 490],
          ].map(([x, y], i) => (
            <path
              key={x}
              d={"M" + (x - 9) + " " + y + "h18M" + x + " " + (y - 9) + "v18"}
              stroke={C.lime}
              strokeWidth="3"
              opacity={ramp(t, reveal + i * 0.08, reveal + 0.3 + i * 0.08)}
            />
          ))}
        </svg>
        {/* Ana, listened to */}
        <div
          style={{
            position: "absolute",
            left: 150,
            top: 330,
            opacity: ramp(t, listen - 0.2, listen + 0.4) * (1 - footage),
            transform: `translateX(${(1 - ramp(t, listen - 0.2, listen + 0.4)) * -60}px)`,
            textAlign: "center",
          }}
        >
          <Portrait
            size={230}
            upset={t >= listen && t < end("investigate_customer")}
          />
          <div style={{ fontSize: 26, marginTop: -14, fontWeight: 600 }}>
            Ana needs help
          </div>
        </div>
        <div
          style={{
            position: "absolute",
            left: 120,
            top: 700,
            width: 640,
            padding: "24px 28px",
            boxSizing: "border-box",
            background: "#f7f5e9",
            color: C.ink,
            borderRadius: 24,
            fontSize: 32,
            lineHeight: 1.35,
            opacity:
              ramp(
                t,
                at("investigate_customer"),
                at("investigate_customer") + 0.25,
              ) *
              (1 -
                ramp(
                  t,
                  end("investigate_customer") + 0.1,
                  end("investigate_customer") + 0.4,
                )),
          }}
        >
          “Please help me.
          <br />
          My money's gone.”
        </div>
        {/* strings from cards (and Ana) to the agent */}
        <svg
          width="1920"
          height="1080"
          style={{ position: "absolute", inset: 0, opacity: 1 - footage }}
        >
          {t > listen && (
            <line
              x1={380}
              y1={470}
              x2={380 + (ORB.x - 380) * ramp(t, listen, listen + 0.8)}
              y2={470}
              stroke={C.mint}
              strokeWidth={4}
              strokeDasharray="10 10"
              strokeDashoffset={-t * 60}
            />
          )}
          {CARDS.map((c, i) => {
            const p = ramp(t, dots + i * 0.15, dots + 0.9 + i * 0.15);
            if (p <= 0) return null;
            return (
              <line
                key={c.key}
                x1={c.x}
                y1={c.y + 60}
                x2={c.x + (ORB.x - c.x) * p}
                y2={c.y + 60 + (ORB.y - c.y - 60) * p}
                stroke="#e45b45"
                strokeWidth={4}
              />
            );
          })}
        </svg>
        {/* the agent */}
        <div
          style={{
            position: "absolute",
            left: orbX - 115,
            top: orbY - 115,
            width: 230,
            textAlign: "center",
            opacity: 1 - footage,
            transform: `scale(${orbP})`,
          }}
        >
          <div
            style={{
              width: 230,
              height: 230,
              borderRadius: 80,
              background: C.mint,
              color: C.ink,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: `0 0 ${70 + Math.sin(t * 3) * 25}px #86e0aa66`,
            }}
          >
            <Icon size={140} />
          </div>
        </div>
        <div
          style={{
            position: "absolute",
            left: orbX - 600,
            top: orbY + 160,
            width: 1200,
            textAlign: "center",
            fontSize: 96 - 62 * settle,
            fontWeight: 700,
            letterSpacing: -3 + 3 * settle,
            whiteSpace: "nowrap",
            opacity: ramp(t, reveal - 0.05, reveal + 0.35) * (1 - footage),
          }}
        >
          Resolution Agent
        </div>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 665,
            textAlign: "center",
            fontSize: 40,
            color: C.mint,
            opacity:
              ramp(t, reveal + 0.1, reveal + 0.6) *
              (1 - ramp(t, listen - 0.9, listen - 0.25)),
          }}
        >
          From panic to a plan.
        </div>
        {/* evidence cards */}
        {CARDS.map((c, i) => {
          if (t < cardAt[i]) return null;
          const p = pop(t, cardAt[i], 0.5);
          return (
            <div
              key={c.key}
              style={{
                position: "absolute",
                left: c.x,
                top: c.y,
                opacity: 1 - footage,
                transform: `scale(${p}) rotate(${(i - 1) * 2.5}deg)`,
              }}
            >
              <Paper rotate={0} style={{ padding: "22px 28px", width: 440 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                    fontSize: 32,
                    fontWeight: 700,
                  }}
                >
                  <Icon kind={c.icon} size={36} /> {c.text}
                </div>
                <div style={{ fontSize: 22, color: "#5f7a68", marginTop: 8 }}>
                  {c.sub}
                </div>
              </Paper>
              <div
                style={{
                  position: "absolute",
                  left: 210,
                  top: -10,
                  width: 22,
                  height: 22,
                  borderRadius: 12,
                  background: "#e45b45",
                  boxShadow: "0 3px 6px #0006",
                }}
              />
            </div>
          );
        })}
        {/* the real recording */}
        {t >= rec && (
          <AbsoluteFill style={{ opacity: footage }}>
            <EvidenceReceipt time={t - rec} />
          </AbsoluteFill>
        )}
      </StoryFrame>
      <Flash at={reveal} color="#b8f2cf" peak={0.28} len={0.35} />
      <Grain />
      <SceneCaptions scene="investigate" />
      <SceneVoice scene="investigate" />
      <Sfx
        name="whoosh"
        at={Math.max(0, reveal - 0.3)}
        volume={0.3}
        rate={1.25}
      />
      <Sfx name="impact" at={reveal} volume={0.27} rate={1.1} />
      <Sfx name="ding" at={reveal + 0.1} volume={0.24} rate={1.25} />
      {cardAt.map((c, i) => (
        <Sfx key={i} name="blip" at={c} volume={0.4} rate={1 + i * 0.12} />
      ))}
      <Sfx name="scan" at={dots} volume={0.35} />
      <Sfx name="scan" at={rec} volume={0.35} rate={1.2} />
      <Sfx name="check" at={tool + 0.7} volume={0.35} />
    </>
  );
};
