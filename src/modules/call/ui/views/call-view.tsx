"use client";

import { Button } from "@/components/ui/button";
import { useTRPC } from "@/trpc/client";
import { useSuspenseQuery } from "@tanstack/react-query";
import { ShieldAlertIcon, VideoOffIcon } from "lucide-react";
import Link from "next/link";
import CallProvider from "../components/call-provider";
import CallStatus from "../components/call-status";

type Props = {
  meetingId: string;
  user: {
    id: string;
    name: string;
    image: string;
  };
};

const CallView = ({ meetingId, user }: Props) => {
  const trpc = useTRPC();

  const { data } = useSuspenseQuery(
    trpc.meetings.getForCall.queryOptions(
      { id: meetingId },
      { refetchOnWindowFocus: false, staleTime: 60_000 }
    )
  );

  if (!data.isJoinable) {
    return (
      <CallStatus
        icon={VideoOffIcon}
        tone="muted"
        title="Meeting has ended"
        description="This meeting is over, so you can no longer join it."
        action={
          <Button asChild>
            <Link href="/meetings">Back to meetings</Link>
          </Button>
        }
      />
    );
  }

  return (
    <CallProvider
      meetingId={meetingId}
      meetingName={data.name}
      agentId={data.agentId}
      isOwner={data.isOwner}
      user={user}
    />
  );
};

export const CallViewLoading = () => {
  return (
    <CallStatus
      loading
      title="Loading meeting"
      description="Please wait while we get the meeting ready."
    />
  );
};

export const CallViewError = () => {
  return (
    <CallStatus
      icon={ShieldAlertIcon}
      tone="danger"
      title="Meeting unavailable"
      description="This meeting does not exist or you do not have access to it."
      action={
        <Button asChild>
          <Link href="/meetings">Back to meetings</Link>
        </Button>
      }
    />
  );
};

export default CallView;