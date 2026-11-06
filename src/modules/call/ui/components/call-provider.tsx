"use client";

import React from "react";
import CallConnect from "./call-connect";

type Props = {
  meetingId: string;
  meetingName: string;
  agentId?: string;
  isOwner: boolean;
  user: {
    id: string;
    name: string;
    image: string;
  };
};

const CallProvider = ({
  meetingId,
  meetingName,
  agentId,
  isOwner,
  user,
}: Props) => {
  return (
    <CallConnect
      meetingId={meetingId}
      meetingName={meetingName}
      agentId={agentId}
      isOwner={isOwner}
      userId={user.id}
      userName={user.name}
      userImage={user.image}
    />
  );
};

export default CallProvider;
