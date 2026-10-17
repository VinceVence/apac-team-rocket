import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Series,
  staticFile,
  useVideoConfig,
  useCurrentFrame,
} from "remotion";
import { Audio } from "@remotion/media";
import { SCENES } from "./script";
import { buildMusicGain } from "./Voice";
import { Cold } from "./Cold";
import { Morning } from "./Morning";
import { Call } from "./Call";
import { After } from "./After";
import { Stakes } from "./Stakes";
import { Investigate } from "./Investigate";
import { Model } from "./Model";
import { Judgment } from "./Judgment";
import { Lesson } from "./Lesson";
import { Intercept } from "./Intercept";
import { Return } from "./Return";

export const SCENE_COMPONENTS: Record<string, React.FC> = {
  cold: Cold,
  morning: Morning,
  call: Call,
  after: After,
  stakes: Stakes,
  investigate: Investigate,
  model: Model,
  judgment: Judgment,
  lesson: Lesson,
  intercept: Intercept,
  return: Return,
};

/** Overall music level. The score carries its own dynamics; this only ducks under voices. */
const MUSIC_LEVEL = 0.4;

export const MintTownStory: React.FC = () => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();
  const gain = useMemo(
    () => buildMusicGain(fps, durationInFrames),
    [fps, durationInFrames],
  );
  return (
    <AbsoluteFill style={{ background: "#030c09" }}>
      <Audio
        name="Continuous story score"
        src={staticFile("audio/story2/score-continuous.mp3")}
        volume={MUSIC_LEVEL * (gain[Math.min(frame, gain.length - 1)] ?? 1)}
      />
      <Series>
        {SCENES.map((s) => {
          const C = SCENE_COMPONENTS[s.id];
          return (
            <Series.Sequence
              key={s.id}
              name={s.title}
              durationInFrames={Math.round(s.duration * fps)}
              premountFor={fps}
            >
              <C />
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};
