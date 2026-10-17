import { MintTownStory, SCENE_COMPONENTS } from "./story/Story";
import { SCENES } from "./story/script";
import React from "react";
import { Composition, Folder } from "remotion";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="MintTown-Story"
      component={MintTownStory}
      durationInFrames={Math.round(SCENES.reduce((n, s) => n + s.duration, 0) * 30)}
      fps={30}
      width={1920}
      height={1080}
    />
    <Folder name="Story-scenes">
      {SCENES.map((s, i) => (
        <Composition
          key={s.id}
          id={`Story-${String(i + 1).padStart(2, "0")}-${s.id}`}
          component={SCENE_COMPONENTS[s.id]}
          durationInFrames={Math.round(s.duration * 30)}
          fps={30}
          width={1920}
          height={1080}
        />
      ))}
    </Folder>
  </>
);
