"use client";

import { StreamTheme, useCall } from "@stream-io/video-react-sdk";
import React, { useState } from "react";
import CallLobby from "./call-lobby";
import CallActive from "./call-active";
import CallEnded from "./call-ended";

type Props = {
  meetingName: string;
};

const CallUI = ({ meetingName }: Props) => {
  const call = useCall();
  const [show, setShow] = useState<"lobby" | "call" | "ended">("lobby");

  const handleJoin = async () => {
    if (!call) return;

    try {
      await call.join();
      setShow("call");
    } catch (error) {
      console.error("Failed to join call:", error);
      // Consider showing an error state or toast notification
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

  return (
    <StreamTheme className="h-[100vh]">
      {show === "lobby" && <CallLobby onJoin={handleJoin} />}
      {show === "call" && (
        <CallActive onLeave={handleLeave} meetingName={meetingName} />
      )}
      {show === "ended" && <CallEnded />}
    </StreamTheme>
  );
};

export default CallUI;
