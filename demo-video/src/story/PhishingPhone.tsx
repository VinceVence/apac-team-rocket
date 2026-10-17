import React from "react";
import { CanvasImage, staticFile } from "remotion";
import { C, Icon } from "./Visuals";
import { pop, ramp, useT } from "./Kit";

/** Illustrated message flow. The .invalid addresses are deliberately nonfunctional. */
export const PhishingPhone: React.FC<{
  pageAt: number;
  requestAt: number;
  transferAt: number;
  resultAt: number;
  protectedPayment?: boolean;
  recipient?: string;
}> = ({
  pageAt,
  requestAt,
  transferAt,
  resultAt,
  protectedPayment = false,
  recipient = "Recipient A",
}) => {
  const t = useT(),
    page = t >= pageAt,
    request = t >= requestAt,
    transfer = t >= transferAt,
    result = t >= resultAt;
  const held = result && protectedPayment,
    enter = ramp(t, 0.1, 0.75);
  const url = protectedPayment ? "mint-verify.invalid" : "mint-secure.invalid";
  return (
    <div
      style={{
        position: "absolute",
        left: 1110,
        top: 110,
        width: 650,
        height: 810,
        boxSizing: "border-box",
        overflow: "hidden",
        borderRadius: 54,
        border: "12px solid " + (held ? "#347d56" : "#193c2e"),
        background: "#f8f9f1",
        color: C.ink,
        boxShadow: held
          ? "0 0 0 10px #b8f2cf44, 0 25px 100px #061a1377"
          : "0 30px 100px #03150ca0",
        opacity: enter,
        transform: "translateY(" + (1 - enter) * 80 + "px)",
        fontFamily: "DM Sans, Arial, sans-serif",
      }}
    >
      <div
        style={{
          width: 114,
          height: 24,
          borderRadius: 20,
          background: "#193c2e",
          margin: "13px auto 22px",
        }}
      />
      {!page ? (
        <div style={{ padding: "18px 36px" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              color: "#6b7e6d",
              fontSize: 21,
            }}
          >
            <span>MESSAGES</span>
            <span>Just now</span>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 18,
              marginTop: 34,
            }}
          >
            <div
              style={{
                background: "#dbeada",
                width: 72,
                height: 72,
                borderRadius: 24,
                display: "grid",
                placeItems: "center",
              }}
            >
              <Icon kind="lock" size={40} />
            </div>
            <div>
              <div style={{ fontSize: 34, fontWeight: 700 }}>Mint Wallet</div>
              <div style={{ fontSize: 20, color: "#8a7560", marginTop: 4 }}>
                Unknown sender
              </div>
            </div>
          </div>
          <div
            style={{
              marginTop: 36,
              background: "#e5eadd",
              borderRadius: "8px 26px 26px 26px",
              padding: 30,
              transform: "scale(" + pop(t, 0.4) + ")",
              transformOrigin: "left top",
            }}
          >
            <div style={{ fontSize: 36, fontWeight: 700, lineHeight: 1.15 }}>
              Unusual activity
              <br />
              on your wallet.
            </div>
            <div style={{ fontSize: 27, lineHeight: 1.4, marginTop: 22 }}>
              Secure your balance
              <br />
              in the next 5 minutes.
            </div>
            <div
              style={{
                color: "#386a9b",
                fontSize: 25,
                textDecoration: "underline",
                marginTop: 24,
              }}
            >
              {url}
            </div>
          </div>
          <div
            style={{
              position: "absolute",
              left: 295,
              top: 485,
              width: 80,
              height: 80,
              border: "4px solid #e6a768",
              borderRadius: 50,
              opacity:
                ramp(t, pageAt - 0.6, pageAt - 0.2) *
                (1 - ramp(t, pageAt - 0.1, pageAt)),
              transform:
                "scale(" + (1.25 - ramp(t, pageAt - 0.6, pageAt) * 0.35) + ")",
            }}
          />
        </div>
      ) : !transfer ? (
        <div>
          <div
            style={{
              margin: "0 26px",
              padding: "14px 20px",
              borderRadius: 14,
              background: "#e7ecdf",
              display: "flex",
              alignItems: "center",
              gap: 14,
              fontSize: 22,
              color: "#59715e",
            }}
          >
            <Icon kind="lock" size={22} />
            {url}
          </div>
          <div
            style={{
              padding: "34px 38px",
              opacity: ramp(t, pageAt, pageAt + 0.25),
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 16,
                fontSize: 32,
                fontWeight: 700,
              }}
            >
              <CanvasImage
                src={staticFile("mark.svg")}
                style={{ width: 48, height: 48 }}
              />
              Mint Wallet
            </div>
            <div
              style={{
                fontSize: 48,
                fontWeight: 700,
                letterSpacing: -1.5,
                marginTop: 36,
              }}
            >
              Protect your balance.
            </div>
            <div style={{ fontSize: 24, color: "#718271", marginTop: 15 }}>
              Security verification
            </div>
            {request && (
              <div
                style={{
                  marginTop: 28,
                  opacity: ramp(t, requestAt, requestAt + 0.4),
                }}
              >
                <div
                  style={{
                    padding: "20px 24px",
                    background: "#edf0dc",
                    borderRadius: 20,
                    fontSize: 28,
                    lineHeight: 1.35,
                  }}
                >
                  Move funds to a<br />
                  <b>“safe account.”</b>
                </div>
                <div style={{ fontSize: 24, color: "#977353", marginTop: 18 }}>
                  Keep this verification private.
                </div>
                <div
                  style={{
                    marginTop: 32,
                    background: "#297551",
                    color: "#f4ffee",
                    borderRadius: 20,
                    padding: "24px 28px",
                    fontSize: 32,
                    fontWeight: 700,
                    textAlign: "center",
                  }}
                >
                  Continue · ₱900
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div
          style={{
            padding: "30px 38px",
            opacity: ramp(t, transferAt, transferAt + 0.2),
          }}
        >
          <div
            style={{
              fontSize: 22,
              color: held ? C.green : "#a25d45",
              letterSpacing: 3,
              fontWeight: 700,
            }}
          >
            {held ? "PAYMENT GUARD" : result ? "TRANSFER SENT" : "TRANSFERRING"}
          </div>
          <div
            style={{
              fontSize: 128,
              fontWeight: 700,
              lineHeight: 1.05,
              letterSpacing: -6,
              marginTop: 34,
            }}
          >
            ₱900
          </div>
          <div style={{ fontSize: 28, color: "#5c745f", marginTop: 18 }}>
            {recipient}
          </div>
          <div
            style={{
              height: 14,
              background: "#e1e6d7",
              borderRadius: 10,
              marginTop: 40,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                height: "100%",
                width:
                  ramp(t, transferAt, resultAt, false) *
                    (protectedPayment ? 80 : 100) +
                  "%",
                background: held ? "#81b77a" : "#da9369",
              }}
            />
          </div>
          {result && (
            <div
              style={{
                marginTop: 38,
                background: held ? "#deefd1" : "#f8e0d3",
                color: held ? C.green : "#9b4838",
                padding: 28,
                borderRadius: 24,
                transform: "scale(" + pop(t, resultAt) + ")",
              }}
            >
              <Icon kind={held ? "shield" : "alert"} size={64} />
              <div
                style={{
                  fontSize: 38,
                  fontWeight: 700,
                  marginTop: 18,
                  lineHeight: 1.12,
                }}
              >
                {held ? "Paused for verification" : "Money sent."}
              </div>
              <div style={{ fontSize: 28, marginTop: 16 }}>
                {held ? "₱0 debited" : "The page stops responding."}
              </div>
            </div>
          )}
        </div>
      )}
      <div
        style={{
          position: "absolute",
          bottom: 14,
          width: 160,
          height: 5,
          left: 233,
          borderRadius: 6,
          background: "#afc3ae",
        }}
      />
    </div>
  );
};
