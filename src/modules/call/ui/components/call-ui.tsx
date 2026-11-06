"use client";

import { useTRPC } from "@/trpc/client";
import { useMutation } from "@tanstack/react-query";
import { StreamTheme, useCall } from "@stream-io/video-react-sdk";
import React, { useEffect, useState } from "react";
import CallLobby from "./call-lobby";
import CallActive from "./call-active";
import CallEnded from "./call-ended";

type Props = {
  meetingId: string;
  meetingName: string;
  agentId?: string;
  isOwner: boolean;
};

const CallUI = ({ meetingId, meetingName, agentId, isOwner }: Props) => {
  const trpc = useTRPC();
  const call = useCall();
  const [show, setShow] = useState<"lobby" | "call" | "ended">("lobby");
  const [joinError, setJoinError] = useState<string | null>(null);

  const { mutateAsync: endMeetingForAll, isPending: isEnding } = useMutation(
    trpc.meetings.endForAll.mutationOptions()
  );

  useEffect(() => {
    if (!call) return;

    return call.on("call.ended", () => setShow("ended"));
  }, [call]);

  const handleJoin = async () => {
    if (!call) return;

    setJoinError(null);

    try {
      await call.join();
      setShow("call");
    } catch (error) {
      console.error("Failed to join call:", error);
      setJoinError(
        error instanceof Error
          ? error.message
          : "Could not join the call. Please try again."
      );
    }
  };

  const handleLeave = async () => {
    if (!call) return;

    try {
      await call.leave();
      setShow("ended");
    } catch (error) {
      console.error("Failed to end call:", error);
      // Still show ended state as fallback
      setShow("ended");
    }
  };

  const handleEndForAll = async () => {
    try {
      await endMeetingForAll({ id: meetingId });
      setShow("ended");
    } catch (error) {
      console.error("Failed to end meeting for all:", error);
    }
  };

  return (
    <StreamTheme className="h-[100vh]">
      {show === "lobby" && <CallLobby onJoin={handleJoin} error={joinError} />}
      {show === "call" && (
        <CallActive
          onLeave={handleLeave}
          meetingName={meetingName}
          agentId={agentId}
          onEndForAll={isOwner ? handleEndForAll : undefined}
          isEnding={isEnding}
        />
      )}
      {show === "ended" && <CallEnded />}
    </StreamTheme>
  );
};

export default CallUI;
