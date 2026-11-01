import type { ReactNode } from "react";

const CallBackdrop = ({ children }: { children: ReactNode }) => (
  <div className="relative flex h-full min-h-screen w-full items-center justify-center overflow-hidden bg-[#060a09] px-6 py-12 text-white">
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 bg-[radial-gradient(120%_80%_at_50%_-20%,rgba(23,207,151,0.16),transparent_65%)]"
    />
    <div
      aria-hidden
      className="pointer-events-none absolute -right-24 -bottom-40 size-[420px] rounded-full bg-[#0f5c47]/25 blur-[140px]"
    />
    <div className="relative z-10 flex w-full flex-col items-center justify-center gap-6">
      {children}
    </div>
  </div>
);

export default CallBackdrop;