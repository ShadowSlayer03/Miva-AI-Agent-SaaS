"use client";

import { Button } from "@/components/ui/button";
import { Link2Icon } from "lucide-react";
import { toast } from "sonner";

type Props = {
  meetingId: string;
};

const CopyInviteLinkButton = ({ meetingId }: Props) => {
  const handleCopy = async () => {
    const url = `${window.location.origin}/call/${meetingId}`;

    try {
      await navigator.clipboard.writeText(url);
      toast.success("Invite link copied to clipboard");
    } catch {
      toast.error("Failed to copy invite link");
    }
  };

  return (
    <Button
      type="button"
      variant="secondary"
      className="w-full lg:w-auto"
      onClick={handleCopy}
    >
      <Link2Icon />
      Copy Invite Link
    </Button>
  );
};

export default CopyInviteLinkButton;