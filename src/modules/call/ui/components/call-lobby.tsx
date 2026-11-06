"use client";

import React, { useState } from "react";

import "@stream-io/video-react-sdk/dist/css/styles.css";
import {
  DefaultVideoPlaceholder,
  StreamVideoParticipant,
  ToggleAudioPreviewButton,
  ToggleVideoPreviewButton,
  useCallStateHooks,
  VideoPreview,
} from "@stream-io/video-react-sdk";
import { authClient } from "@/lib/auth-client";
import generateAvatarURI from "@/lib/avatar";
import { Button } from "@/components/ui/button";
import { LogInIcon } from "lucide-react";
import Link from "next/link";
import CallBackdrop from "./call-backdrop";

type Props = {
  onJoin: () => void;
  error?: string | null;
};

const DisabledVideoPreview = () => {
  const { data } = authClient.useSession();

  return (
    <DefaultVideoPlaceholder
      participant={
        {
          name: data?.user.name ?? "",
          image:
            data?.user.image ??
            generateAvatarURI({
              seed: data?.user.name ?? "",
              variant: "initials",
            }),
        } as StreamVideoParticipant
      }
    />
  );
};

const AllowBrowserPermissions = () => {
  return (
    <p className="max-w-xs px-6 text-center text-sm text-muted-foreground">
      Please grant your browser permission to access your camera and microphone.
    </p>
  );
};

const CallLobby = ({ onJoin, error }: Props) => {
  const { useCameraState, useMicrophoneState } = useCallStateHooks();

  const { hasBrowserPermission: hasMicPermission } = useMicrophoneState();
  const { hasBrowserPermission: hasCameraPermission } = useCameraState();

  const hasBrowserMediaPermission = hasMicPermission && hasCameraPermission;

  const [loading,setLoading] = useState(false);

  const handleClickOnJoin = async()=>{
    setLoading(true);
    await onJoin();
    setLoading(false);
  }

  return (
    <CallBackdrop>
      <div className="flex w-full max-w-xl flex-col items-center justify-center gap-y-6 rounded-lg bg-background p-10 text-foreground shadow-sm">
        <div className="flex flex-col gap-y-2 text-center">
          <h6 className="text-lg font-medium">Ready to join?</h6>
          <p className="text-sm text-muted-foreground">
            Set up your call before joining
          </p>
        </div>
        <div className="miva-lobby w-full">
          <VideoPreview
            DisabledVideoPreview={
              hasBrowserMediaPermission
                ? DisabledVideoPreview
                : AllowBrowserPermissions
            }
          />
        </div>
        <div className="flex gap-x-2">
          <ToggleAudioPreviewButton />
          <ToggleVideoPreviewButton />
        </div>
        {error && (
          <p className="max-w-sm text-center text-sm text-red-500">{error}</p>
        )}
        <div className="flex w-full justify-between gap-x-2">
          <Button asChild variant="ghost">
            <Link href="/meetings">Cancel</Link>
          </Button>
          <Button disabled={loading} onClick={handleClickOnJoin}>
            <LogInIcon />
            {loading ? "Joining..." : "Join Call"}
          </Button>
        </div>
      </div>
    </CallBackdrop>
  );
};

export default CallLobby;
