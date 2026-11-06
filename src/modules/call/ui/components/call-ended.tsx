import { Button } from "@/components/ui/button";
import { CheckCircle2Icon } from "lucide-react";
import Link from "next/link";

import "@stream-io/video-react-sdk/dist/css/styles.css";
import CallStatus from "./call-status";

const CallEnded = () => {
  return (
    <CallStatus
      icon={CheckCircle2Icon}
      title="You have ended the call"
      description="The summary will appear in a few minutes, once the recording has been processed."
      action={
        <Button asChild>
          <Link href="/meetings">Back to meetings</Link>
        </Button>
      }
    />
  );
};

export default CallEnded;