"use client";

import React, { useEffect, useState } from "react";

import "@stream-io/video-react-sdk/dist/css/styles.css";
import { useTRPC } from "@/trpc/client";
import { useMutation } from "@tanstack/react-query";
import {
  Call,
  CallingState,
  StreamCall,
  StreamVideo,
  StreamVideoClient,
} from "@stream-io/video-react-sdk";
import CallStatus from "./call-status";
import CallUI from "./call-ui";

type Props = {
  meetingId: string;
  meetingName: string;
  agentId?: string;
  isOwner: boolean;
  userId: string;
  userName: string;
  userImage: string;
};

const CallConnect = ({
  meetingId,
  meetingName,
  agentId,
  isOwner,
  userId,
  userName,
  userImage,
}: Props) => {
  const trpc = useTRPC();
  const { mutateAsync: generateToken } = useMutation(
    trpc.meetings.generateToken.mutationOptions()
  );

  const [client, setClient] = useState<StreamVideoClient>();

  useEffect(() => {
    const _client = new StreamVideoClient({
      apiKey: process.env.NEXT_PUBLIC_STREAM_VIDEO_API_KEY!,
      user: {
        id: userId,
        name: userName,
        image: userImage,
      },
      tokenProvider: generateToken,
    });

    setClient(_client);

    return () => {
      void _client.disconnectUser();
    };
  }, [userId, userName, userImage, generateToken]);

  const [call, setCall] = useState<Call>();

  useEffect(() => {
    if (!client) return;

    const _call = client.call("default", meetingId);

    _call.camera.disable();
    _call.microphone.disable();
    setCall(_call);

    return () => {
      if (_call.state.callingState !== CallingState.LEFT) {
        void _call.leave().catch((error) => {
          console.error("[CallConnect] Cleanup leave failed", error);
        });
      }
    };
  }, [client, meetingId]);

  if (!client || !call)
    return (
      <CallStatus
        loading
        title="Joining the meeting"
        description="Setting up your connection and video preview."
      />
    );

  return (
    <StreamVideo client={client}>
      <StreamCall call={call}>
        <CallUI
          meetingId={meetingId}
          meetingName={meetingName}
          agentId={agentId}
          isOwner={isOwner}
        />
      </StreamCall>
    </StreamVideo>
  );
};

export default CallConnect;