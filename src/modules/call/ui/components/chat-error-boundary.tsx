"use client";

import { TriangleAlertIcon } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  title?: string;
};

type State = {
  hasError: boolean;
};

/**
 * Keeps a broken panel from taking the whole call down.
 *
 * The call lives in the same React tree as the chat, so without a local
 * boundary a single render/effect error inside the chat unmounts `CallConnect`
 * too — and its cleanup leaves the Stream call. The boundary contains the
 * damage to the panel itself.
 */
class ChatErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[CallChat] The meeting chat crashed", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
        <TriangleAlertIcon className="size-5 text-white/40" />
        <p className="text-sm text-white/60">
          {this.props.title ?? "The meeting chat could not be displayed."}
        </p>
        <button
          type="button"
          onClick={() => this.setState({ hasError: false })}
          className="rounded-full bg-white/10 px-3 py-1.5 text-xs text-white/80 transition-colors hover:bg-white/15 hover:text-white"
        >
          Try again
        </button>
      </div>
    );
  }
}

export default ChatErrorBoundary;