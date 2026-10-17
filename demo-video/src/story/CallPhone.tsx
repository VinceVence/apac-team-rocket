import React from "react";
import { C, Icon } from "./Visuals";
import { ramp, pop, Waveform, useT } from "./Kit";

export type CallCard = { at: number; text: React.ReactNode; tone?: "danger" | "plain" | "secret" };

/**
 * The phone used for both calls (Ana, then Jun) so the second call visually rhymes with the first.
 * All times are scene-local seconds.
 */
export const CallPhone: React.FC<{
  x?: number;
  y?: number;
  enterAt?: number;
  ringUntil: number;
  callerTalking: boolean;
  cards: CallCard[];
  transferAt: number;
  sentAt: number;
  recipient: string;
  /** If set, the transfer is held at this time instead of sent. */
  heldAt?: number;
  endedAt?: number;
  footer?: React.ReactNode;
}> = ({
  x = 1170,
  y = 120,
  enterAt = 0.3,
  ringUntil,
  callerTalking,
  cards,
  transferAt,
  sentAt,
  recipient,
  heldAt,
  endedAt,
  footer,
}) => {
  const t = useT();
  const enter = ramp(t, enterAt, enterAt + 0.7);
  const ringing = t < ringUntil;
  const transfer = t >= transferAt;
  const held = heldAt !== undefined && t >= heldAt;
  const sent = !held && heldAt === undefined && t >= sentAt;
  const ended = endedAt !== undefined && t >= endedAt;
  const shake = ringing ? Math.sin(t * 60) * 2.2 * (Math.sin(t * 8) > 0 ? 1 : 0) : 0;
  const callSecs = Math.max(0, Math.floor(t - ringUntil));
  const frame = held ? "#2f7a59" : transfer || ended ? "#5a2c24" : "#163a2c";
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: 580,
        height: 820,
        borderRadius: 52,
        background: "#f7f8ef",
        color: C.ink,
        border: `13px solid ${frame}`,
        boxShadow: held
          ? "0 0 0 10px #b8f2cf55, 0 30px 120px #6ee0a066"
          : "0 30px 110px #02100b99",
        opacity: enter,
        transform: `translateY(${(1 - enter) * 90}px) rotate(${shake + (1 - enter) * 4}deg)`,
        overflow: "hidden",
        fontFamily: "DM Sans, Arial, sans-serif",
      }}
    >
      <div style={{ width: 120, height: 26, borderRadius: 18, background: "#163a2c", margin: "12px auto 0" }} />
      {!transfer ? (
        <div style={{ padding: "34px 38px" }}>
          <div style={{ fontSize: 19, letterSpacing: 3, color: "#a0563f", fontWeight: 600 }}>
            {ringing ? "INCOMING CALL" : ended ? "CALL ENDED" : `ON CALL · 00:${String(callSecs).padStart(2, "0")}`}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 22, marginTop: 22 }}>
            <div
              style={{
                width: 92,
                height: 92,
                borderRadius: 50,
                background: "#efe1d4",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#a0563f",
                boxShadow: ringing ? `0 0 0 ${10 + 10 * Math.abs(Math.sin(t * 5))}px #e9b9a133` : "none",
              }}
            >
              <Icon kind="lock" size={52} />
            </div>
            <div>
              <div style={{ fontSize: 40, fontWeight: 700, lineHeight: 1.05 }}>Mint Bank Security</div>
              <div style={{ fontSize: 21, color: "#9a6a55", marginTop: 6 }}>Unverified caller</div>
            </div>
          </div>
          <div style={{ marginTop: 30, height: 70 }}>
            {!ringing && !ended && <Waveform active={callerTalking} />}
          </div>
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 16 }}>
            {cards.map((c, i) => {
              const p = pop(t, c.at);
              if (t < c.at) return null;
              const bg = c.tone === "danger" ? "#fbe3d9" : c.tone === "secret" ? "#2a1612" : "#e8eedf";
              const fg = c.tone === "secret" ? "#ffd9c9" : c.tone === "danger" ? "#8a3424" : C.ink;
              return (
                <div
                  key={i}
                  style={{
                    background: bg,
                    color: fg,
                    padding: "18px 22px",
                    borderRadius: 18,
                    fontSize: 29,
                    lineHeight: 1.25,
                    fontWeight: 600,
                    transform: `scale(${p})`,
                    transformOrigin: "left center",
                  }}
                >
                  {c.text}
                </div>
              );
            })}
          </div>
          {ringing && (
            <div style={{ position: "absolute", bottom: 70, left: 0, right: 0, display: "flex", justifyContent: "space-around" }}>
              <div style={{ width: 92, height: 92, borderRadius: 50, background: "#b34b3a" }} />
              <div
                style={{
                  width: 92,
                  height: 92,
                  borderRadius: 50,
                  background: "#2f8a5e",
                  transform: `scale(${1 + 0.08 * Math.abs(Math.sin(t * 6))})`,
                }}
              />
            </div>
          )}
        </div>
      ) : (
        <div style={{ padding: "34px 38px" }}>
          <div style={{ fontSize: 19, letterSpacing: 3, color: held ? C.green : "#a0563f", fontWeight: 700 }}>
            {held ? "PAYMENT GUARD" : sent ? "TRANSFER SENT" : "SENDING…"}
          </div>
          <div style={{ fontSize: 120, fontWeight: 700, letterSpacing: -4, marginTop: 18 }}>₱900</div>
          <div style={{ fontSize: 22, color: "#6c7c6a", marginTop: 4 }}>To a new recipient</div>
          <div style={{ fontSize: 30, fontWeight: 600, marginTop: 6, overflowWrap: "anywhere" }}>{recipient}</div>
          <div style={{ height: 14, background: "#e2e8da", borderRadius: 8, marginTop: 34, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${
                  heldAt !== undefined
                    ? ramp(t, transferAt, heldAt, false) * 82
                    : ramp(t, transferAt, sentAt, false) * 100
                }%`,
                background: held ? "#e2a54d" : sent ? "#b34b3a" : "#e2a54d",
              }}
            />
          </div>
          {held ? (
            <div
              style={{
                marginTop: 34,
                background: "#d9f2cc",
                color: C.green,
                padding: "26px 26px",
                borderRadius: 20,
                display: "flex",
                alignItems: "center",
                gap: 20,
                fontSize: 38,
                fontWeight: 700,
                transform: `scale(${pop(t, heldAt!, 0.4)})`,
              }}
            >
              <Icon kind="shield" size={64} /> Held before debit
            </div>
          ) : sent ? (
            <div style={{ marginTop: 34, fontSize: 30, lineHeight: 1.4, color: "#8b3e2f", fontWeight: 600 }}>
              Sent.
              {ended && (
                <div style={{ fontSize: 26, color: "#9a6a55", fontWeight: 500, marginTop: 14 }}>
                  Call ended. The number no longer answers.
                </div>
              )}
            </div>
          ) : null}
          {footer && <div style={{ marginTop: 28 }}>{footer}</div>}
        </div>
      )}
      <div style={{ position: "absolute", bottom: 16, left: "37%", width: "26%", height: 6, background: "#b8c8b8", borderRadius: 5 }} />
    </div>
  );
};
