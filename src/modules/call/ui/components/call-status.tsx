import { Loader2Icon, type LucideIcon } from "lucide-react";
import Image from "next/image";
import type { ReactNode } from "react";
import CallBackdrop from "./call-backdrop";

type Tone = "brand" | "danger" | "muted";

type Props = {
  title: string;
  description: string;
  icon?: LucideIcon;
  tone?: Tone;
  loading?: boolean;
  action?: ReactNode;
};

const TONES: Record<Tone, { chip: string; icon: string }> = {
  brand: {
    chip: "border-primary/20 bg-primary/10",
    icon: "text-primary",
  },
  danger: {
    chip: "border-red-200 bg-red-50",
    icon: "text-red-500",
  },
  muted: {
    chip: "border-border bg-muted",
    icon: "text-muted-foreground",
  },
};

/**
 * A centered status card (loading, error, ended) on the call backdrop.
 *
 * The page behind it stays near-black, but the card itself uses the same
 * `bg-background` dialog styling as the rest of the app.
 */
const CallStatus = ({
  title,
  description,
  icon: Icon,
  tone = "brand",
  loading = false,
  action,
}: Props) => {
  const palette = TONES[tone];

  return (
    <CallBackdrop>
      <span className="flex items-center gap-2 text-[11px] font-medium tracking-[0.18em] text-white/40 uppercase">
        <Image src="/logo.svg" width={16} height={16} alt="" />
        Miva AI
      </span>

      <div className="flex w-full max-w-md flex-col items-center justify-center gap-y-6 rounded-lg bg-background p-10 text-foreground shadow-sm">
        <div
          className={`flex size-12 items-center justify-center rounded-full border ${palette.chip}`}
        >
          {loading ? (
            <Loader2Icon className={`size-5 animate-spin ${palette.icon}`} />
          ) : Icon ? (
            <Icon className={`size-5 ${palette.icon}`} />
          ) : (
            <Image src="/logo.svg" width={20} height={20} alt="" />
          )}
        </div>

        <div className="flex flex-col gap-y-2 text-center">
          <h6 className="text-lg font-medium">{title}</h6>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>

        {action}
      </div>
    </CallBackdrop>
  );
};

export default CallStatus;