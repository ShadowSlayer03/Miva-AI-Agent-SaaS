"use client";

import {
  CallControls,
  ParticipantView,
  SpeakerLayout,
  useCall,
  useCallStateHooks,
} from "@stream-io/video-react-sdk";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

type Props = {
  onLeave: () => void;
  meetingName: string;
  agentId?: string;
};

type SlideEvent = {
  type?: string;
  active?: boolean;
  title?: string;
};

const CallActive = ({ onLeave, meetingName, agentId }: Props) => {
  const call = useCall();
  const { useParticipants } = useCallStateHooks();
  const participants = useParticipants();
  const [slideTitle, setSlideTitle] = useState<string | null>(null);

  useEffect(() => {
    if (!call) return;

    const unsubscribe = call.on("custom", (event) => {
      const payload = event.custom as SlideEvent | undefined;
      if (payload?.type !== "slide") return;
      setSlideTitle(payload.active ? payload.title ?? "Visual" : null);
    });

    return unsubscribe;
  }, [call]);

  const agent = participants.find((p) => p.userId === agentId);
  const humans = participants.filter((p) => p.userId !== agentId);
  const isRecording = call?.state.recording;

  return (
    <div className="flex h-full flex-col gap-3 p-4 text-white">
      <div className="flex items-center gap-4 rounded-full bg-[#101213] p-4">
        <Link
          href="/"
          className="flex w-fit items-center justify-center rounded-full bg-white/10 p-1"
        >
          <Image src="/logo.svg" width={22} height={22} alt="Logo" />
        </Link>
        <h4 className="text-base">{meetingName}</h4>

        <div className="ml-auto flex items-center gap-3 text-xs text-white/60">
          {isRecording && (
            <span className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-red-500" />
              REC
            </span>
          )}
          <span className="flex items-center gap-2">
            <span
              className={`size-2 rounded-full ${
                slideTitle ? "bg-[#17cf97]" : "bg-[#17cf97]/40"
              }`}
            />
            {slideTitle ? `Presenting: ${slideTitle}` : "Live"}
          </span>
        </div>
      </div>

      {agent ? (
        <div className={`grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto lg:overflow-hidden ${
            humans.length > 0
              ? "lg:grid-cols-[minmax(0,1fr)_180px]"
              : "lg:grid-cols-1"
          }`}>
          <div className="relative aspect-video min-h-0 overflow-hidden rounded-xl bg-black lg:aspect-auto">
            <ParticipantView
              participant={agent}
              trackType="videoTrack"
              mirror={false}
              muteAudio={false}
              ParticipantViewUI={null}
              className="miva-stage h-full w-full"
            />
          </div>

          <div className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-y-auto">
            {humans.map((participant) => (
              <div
                key={participant.sessionId}
                className="aspect-video min-w-[140px] overflow-hidden rounded-lg bg-[#101213]"
              >
                <ParticipantView
                  participant={participant}
                  trackType="videoTrack"
                  className="h-full w-full"
                />
              </div>
            ))}
          </div>
        </div>
      ) : (
        <SpeakerLayout />
      )}

      <div className="rounded-full bg-[#101213] px-4">
        <CallControls onLeave={onLeave} />
      </div>
    </div>
  );
};

export default CallActive;
