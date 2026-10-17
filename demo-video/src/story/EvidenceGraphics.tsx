import React from "react";
import { AbsoluteFill } from "remotion";
import { C, Icon } from "./Visuals";
import { ramp, pop } from "./Kit";

// Amount in saved case SC-a1a870cc4e; see docs/visual-demo.md and README provenance.
const CASE_AMOUNT_PHP = 900;

const surface: React.CSSProperties = {
  background: "#f5f7e9",
  color: C.ink,
  borderRadius: 28,
  boxShadow: "0 24px 75px #03150d70",
};
const background = "radial-gradient(ellipse at 50% 45%,#204a37,#092218 75%)";

/** Clean vector representations of the saved tool receipts, not screenshots or a new live run. */
export const EvidenceReceipt: React.FC<{ time: number }> = ({ time: t }) => (
  <AbsoluteFill style={{ background }}>
    <div
      style={{
        position: "absolute",
        left: 120,
        top: 130,
        color: C.mint,
        fontSize: 26,
        letterSpacing: 3,
      }}
    >
      BUILT FOR THE ANALYST
    </div>
    <div
      style={{
        position: "absolute",
        left: 120,
        top: 190,
        fontSize: 74,
        fontWeight: 700,
        letterSpacing: -3,
      }}
    >
      A clearer case. In one place.
    </div>
    <svg width="1920" height="1080" style={{ position: "absolute", inset: 0 }}>
      {[410, 580, 750].map((y, i) => (
        <g key={y}>
          <path
            d={"M650 " + y + " C820 " + y + ",820 580,1000 580"}
            stroke="#8cb69b"
            strokeWidth="4"
            fill="none"
            strokeDasharray="8 12"
          />
          <circle
            cx={650 + 350 * ramp(t, 0.3 + i * 0.25, 1.2 + i * 0.25)}
            cy={y + (580 - y) * ramp(t, 0.3 + i * 0.25, 1.2 + i * 0.25)}
            r="11"
            fill={C.lime}
          />
        </g>
      ))}
      <path d="M1190 580 H1380" stroke={C.mint} strokeWidth="4" fill="none" />
      <path
        d="m1360 568 20 12-20 12"
        stroke={C.mint}
        strokeWidth="4"
        fill="none"
      />
    </svg>
    {[
      {
        y: 335,
        kind: "book",
        title: "Customer report",
        value: "A claim to verify",
      },
      {
        y: 505,
        kind: "data",
        title: "Verified transfer",
        value: "₱" + CASE_AMOUNT_PHP,
      },
      {
        y: 675,
        kind: "data",
        title: "Wallet history",
        value: "Before the complaint",
      },
    ].map((c, i) => (
      <div
        key={c.title}
        style={{
          ...surface,
          position: "absolute",
          left: 120,
          top: c.y,
          width: 530,
          height: 135,
          padding: "24px 30px",
          boxSizing: "border-box",
          display: "flex",
          alignItems: "center",
          gap: 24,
          opacity: ramp(t, i * 0.2, 0.5 + i * 0.2),
        }}
      >
        <Icon kind={c.kind} size={58} />
        <div>
          <div style={{ fontSize: 24, color: "#688166" }}>{c.title}</div>
          <div style={{ fontSize: 34, fontWeight: 700, marginTop: 5 }}>
            {c.value}
          </div>
        </div>
      </div>
    ))}
    <div
      style={{
        position: "absolute",
        left: 1000,
        top: 480,
        width: 190,
        textAlign: "center",
      }}
    >
      <div
        style={{
          height: 190,
          borderRadius: 55,
          background: C.mint,
          color: C.ink,
          display: "grid",
          placeItems: "center",
          boxShadow: "0 0 75px #b8f2cf22",
          transform: "scale(" + pop(t, 0.4) + ")",
        }}
      >
        <Icon size={116} />
      </div>
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          width: 340,
          marginLeft: -75,
          marginTop: 25,
        }}
      >
        Resolution agent
      </div>
    </div>
    <div
      style={{
        ...surface,
        position: "absolute",
        left: 1400,
        top: 430,
        width: 370,
        height: 300,
        padding: 38,
        boxSizing: "border-box",
        transform: "rotate(2deg)",
        opacity: ramp(t, 1, 1.6),
      }}
    >
      <Icon kind="lock" size={62} />
      <div
        style={{
          fontSize: 42,
          fontWeight: 700,
          lineHeight: 1.1,
          marginTop: 22,
        }}
      >
        Evidence
        <br />
        snapshot
      </div>
      <div style={{ fontSize: 25, color: C.green, marginTop: 18 }}>
        Frozen for review
      </div>
    </div>
  </AbsoluteFill>
);

export const ModelToolFlow: React.FC<{ time: number }> = ({ time: t }) => (
  <AbsoluteFill style={{ background }}>
    <div
      style={{
        position: "absolute",
        left: 120,
        top: 130,
        fontSize: 26,
        letterSpacing: 3,
        color: C.mint,
      }}
    >
      THE AGENT CHOOSES A TOOL
    </div>
    <div
      style={{
        position: "absolute",
        left: 120,
        top: 190,
        fontSize: 75,
        fontWeight: 700,
        letterSpacing: -3,
      }}
    >
      Models, used where they help.
    </div>
    <svg width="1920" height="1080" style={{ position: "absolute", inset: 0 }}>
      <path d="M580 495 H1340" stroke="#91bc9d" strokeWidth="4" fill="none" />
      <path
        d="m1320 483 20 12-20 12"
        stroke="#91bc9d"
        strokeWidth="4"
        fill="none"
      />
      <circle
        cx={580 + 760 * ramp(t, 0.1, 1.25)}
        cy="495"
        r="13"
        fill={C.lime}
      />
      <path
        d="M1340 640 H580"
        stroke="#eeb491"
        strokeWidth="4"
        fill="none"
        opacity={ramp(t, 1.25, 1.7)}
      />
      <path
        d="m600 628-20 12 20 12"
        stroke="#eeb491"
        strokeWidth="4"
        fill="none"
        opacity={ramp(t, 1.25, 1.7)}
      />
      <circle
        cx={1340 - 760 * ramp(t, 1.3, 2.8)}
        cy="640"
        r="13"
        fill="#eeb491"
        opacity={ramp(t, 1.3, 1.5)}
      />
    </svg>
    {[
      { x: 320, kind: "agent", title: "Resolution agent", bg: C.mint },
      { x: 1340, kind: "model", title: "Fraud classifier", bg: "#e8e8bd" },
    ].map((c) => (
      <div
        key={c.title}
        style={{
          position: "absolute",
          left: c.x,
          top: 410,
          width: 260,
          textAlign: "center",
        }}
      >
        <div
          style={{
            height: 260,
            borderRadius: 64,
            background: c.bg,
            color: C.ink,
            display: "grid",
            placeItems: "center",
            transform: "scale(" + pop(t, 0.05) + ")",
          }}
        >
          <Icon kind={c.kind} size={150} />
        </div>
        <div
          style={{
            fontSize: 35,
            fontWeight: 700,
            marginTop: 28,
            whiteSpace: "nowrap",
            marginLeft: -55,
            width: 370,
          }}
        >
          {c.title}
        </div>
      </div>
    ))}
    <div
      style={{
        position: "absolute",
        left: 640,
        top: 410,
        width: 640,
        textAlign: "center",
        fontSize: 29,
        color: "#d6e9c9",
      }}
    >
      Relevant case data
    </div>
    <div
      style={{
        position: "absolute",
        left: 640,
        top: 665,
        width: 640,
        textAlign: "center",
        fontSize: 29,
        color: "#f0c3a0",
        opacity: ramp(t, 1.3, 1.7),
      }}
    >
      Model findings returned
    </div>
  </AbsoluteFill>
);
