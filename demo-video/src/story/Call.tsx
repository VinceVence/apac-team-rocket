import React from "react";
import { interpolate } from "remotion";
import { Town } from "./World";
import { StoryFrame } from "./Visuals";
import { SceneCaptions, SceneVoice, Sfx } from "./Voice";
import { PhishingPhone } from "./PhishingPhone";
import { clamp, Dread, Grain, ramp, useT } from "./Kit";
import { at, word } from "./script";

export const Call: React.FC = () => {
  const t = useT(),
    pageAt = at("phishing_2"),
    requestAt = at("phishing_3") - 0.15;
  const transferAt = at("phishing_4") - 0.3,
    sentAt = word("phishing_4", "disappear");
  const zoom = interpolate(t, [0, 5, 20], [1.32, 1.75, 2], clamp);
  return (
    <>
      <StoryFrame brand="town" label="Illustrated phishing scenario">
        <Town
          time={17.5 + t}
          zoom={zoom}
          cx={600 + 440 / (2 * zoom)}
          cy={470}
          mode={t >= sentAt ? "panic" : "scam"}
          quiet
          dark={interpolate(t, [0, 12, 20], [0.02, 0.3, 0.55], clamp)}
        />
        <Dread intensity={ramp(t, pageAt, transferAt, false)} bpm={90} />
        <div
          style={{
            position: "absolute",
            left: 100,
            top: 130,
            opacity: ramp(t, 0.1, 0.8) * (1 - ramp(t, 4, 4.6)),
            textShadow: "0 4px 24px #062316",
          }}
        >
          <div style={{ fontSize: 27, letterSpacing: 4, color: "#f9dfac" }}>
            ONE MESSAGE
          </div>
          <div
            style={{
              fontSize: 86,
              fontWeight: 700,
              letterSpacing: -3,
              lineHeight: 1.05,
              marginTop: 14,
            }}
          >
            Everything
            <br />
            changes.
          </div>
        </div>
        {t >= pageAt && t < transferAt && (
          <div
            style={{
              position: "absolute",
              left: 110,
              top: 680,
              background: "#153628dd",
              borderRadius: 22,
              padding: "24px 30px",
              fontSize: 31,
              opacity: ramp(t, pageAt + 0.3, pageAt + 0.9),
            }}
          >
            {t < requestAt
              ? "Familiar branding. Unfamiliar link."
              : "Urgency → trust → transfer"}
          </div>
        )}
        <PhishingPhone
          pageAt={pageAt}
          requestAt={requestAt}
          transferAt={transferAt}
          resultAt={sentAt}
        />
      </StoryFrame>
      <Grain />
      <SceneCaptions scene="call" />
      <SceneVoice scene="call" />
      <Sfx name="blip" at={0.4} volume={0.52} />
      <Sfx name="blip" at={pageAt} volume={0.25} />
      <Sfx name="whoosh" at={transferAt} volume={0.3} />
      <Sfx name="ding_sour" at={sentAt} volume={0.4} />
    </>
  );
};
