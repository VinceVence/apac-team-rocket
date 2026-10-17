import React from "react";
import { StoryFrame, Paper, Icon, C } from "./Visuals";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { Grain, Highlight, pop, ramp, useT } from "./Kit";
import { word, at } from "./script";

export const Judgment: React.FC = () => {
  const t = useT(),
    human = word("judgment_2", "human"),
    decide = word("judgment_2", "decides"),
    benefit = at("judgment_3");
  return (
    <>
      <StoryFrame label="Supporting human fraud analysts">
        <div
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(ellipse at 50% 50%,#204a37,#092218 75%)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 130,
            top: 140,
            fontSize: 74,
            fontWeight: 700,
            letterSpacing: -3,
          }}
        >
          A clearer case. A human decision.
        </div>
        <div
          style={{
            position: "absolute",
            left: 150,
            top: 310,
            width: 870,
            transform: "scale(" + pop(t, 0.1) + ")",
          }}
        >
          <Paper rotate={-1} style={{ padding: 44 }}>
            <div
              style={{
                display: "flex",
                gap: 20,
                alignItems: "center",
                fontSize: 27,
                color: C.green,
                fontWeight: 700,
              }}
            >
              <Icon size={54} />
              RESOLUTION AGENT
            </div>
            <div style={{ fontSize: 46, fontWeight: 700, marginTop: 24 }}>
              Ready for the fraud analyst
            </div>
            {["Customer concern", "Transaction evidence", "Model findings"].map(
              (label, i) => (
                <div
                  key={label}
                  style={{
                    display: "flex",
                    gap: 18,
                    alignItems: "center",
                    marginTop: 24,
                    fontSize: 32,
                    opacity: ramp(t, 0.6 + i * 0.35, 1.1 + i * 0.35),
                  }}
                >
                  <Icon kind="check" size={34} color={C.green} />
                  {label}
                </div>
              ),
            )}
          </Paper>
        </div>
        <svg
          width="1920"
          height="1080"
          style={{
            position: "absolute",
            inset: 0,
            opacity: ramp(t, human, human + 0.4),
          }}
        >
          <path
            d="M1060 540 H1290m-20-12 20 12-20 12"
            stroke={C.mint}
            strokeWidth="4"
            fill="none"
          />
        </svg>
        <div
          style={{
            position: "absolute",
            left: 1340,
            top: 350,
            width: 360,
            textAlign: "center",
            opacity: ramp(t, human, human + 0.4),
          }}
        >
          <div
            style={{
              width: 240,
              height: 240,
              borderRadius: 80,
              margin: "0 auto",
              background: "#ecdfc1",
              color: C.ink,
              display: "grid",
              placeItems: "center",
              transform: "scale(" + pop(t, human) + ")",
            }}
          >
            <Icon kind="person" size={140} />
          </div>
          <div style={{ fontSize: 42, fontWeight: 700, marginTop: 25 }}>
            Fraud analyst
          </div>
          <div style={{ fontSize: 29, color: C.mint, marginTop: 20 }}>
            Verify · review · decide
          </div>
        </div>
        {t >= decide && (
          <div
            style={{
              position: "absolute",
              left: 640,
              top: 680,
              padding: "16px 28px",
              border: "6px solid #b8f2cf",
              borderRadius: 12,
              fontSize: 43,
              fontWeight: 700,
              color: C.mint,
              transform: "scale(" + pop(t, decide) + ") rotate(-7deg)",
            }}
          >
            HUMAN REVIEW
          </div>
        )}
        <div
          style={{
            position: "absolute",
            left: 130,
            top: 830,
            fontSize: 34,
            color: C.lime,
            opacity: ramp(t, benefit, benefit + 0.4),
          }}
        >
          Less time gathering data. More time helping the customer.
        </div>
        <Highlight at={human} x={1400} y={350} width={240} height={240} color="#ecdfc1" />
        <Highlight at={decide} x={640} y={680} width={395} height={100} />
      </StoryFrame>
      <Grain />
      <SceneCaptions scene="judgment" />
      <SceneVoice scene="judgment" />
      <Sfx name="check" at={human} volume={0.4} />
      <Sfx name="stamp" at={decide} volume={0.58} />
    </>
  );
};
