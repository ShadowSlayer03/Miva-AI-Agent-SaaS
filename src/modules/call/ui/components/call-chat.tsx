"use client";

import { useTRPC } from "@/trpc/client";
import { useMutation } from "@tanstack/react-query";
import { Loader2Icon, MessagesSquareIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { Channel as StreamChannel } from "stream-chat";
import { StreamChat } from "stream-chat";
import {
  Channel,
  Chat,
  MessageInput,
  MessageList,
  Window,
} from "stream-chat-react";
import "stream-chat-react/dist/css/v2/index.css";

type Props = {
  meetingId: string;
  user: {
    id: string;
    name: string;
    image?: string;
  };
};

const CHAT_API_KEY = process.env.NEXT_PUBLIC_STREAM_CHAT_API_KEY;

/**
 * The meeting chat, rendered next to the call.
 *
 * This is where the agent's `post_link` messages land: the Python agent writes
 * to `messaging:<meetingId>` server-side, and this panel watches the very same
 * channel. It reuses the chat token endpoint the app already exposes, so the
 * signed-in user joins as themselves.
 */
const CallChat = ({ meetingId, user }: Props) => {
  const trpc = useTRPC();
  const { mutateAsync: generateToken } = useMutation(
    trpc.meetings.generateChatToken.mutationOptions()
  );

  const [client, setClient] = useState<StreamChat>();
  const [channel, setChannel] = useState<StreamChannel>();
  const [error, setError] = useState<string | null>(null);

  // `mutateAsync` is not guaranteed to keep its identity across renders, so it
  // is read through a ref. Using it as an effect dependency would tear the chat
  // down every time the token request settles.
  const tokenRef = useRef(generateToken);
  tokenRef.current = generateToken;

  // Strict Mode mounts, unmounts and mounts again. Tearing the connection down
  // immediately would race the second connect, so the teardown is deferred and
  // cancelled by the remount. The in-flight connect is kept here so a remount
  // can await it instead of starting a second, competing connection.
  const connectRef = useRef<{
    userId: string;
    promise: Promise<void>;
  } | null>(null);
  const teardownRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!CHAT_API_KEY) return;

    if (teardownRef.current) {
      clearTimeout(teardownRef.current);
      teardownRef.current = null;
    }

    let active = true;
    const chatClient = StreamChat.getInstance(CHAT_API_KEY);
    const meetingChannel = chatClient.channel("messaging", meetingId);
    setError(null);

    const connect = async () => {
      if (chatClient.userID !== user.id) {
        const pending = connectRef.current;
        if (pending?.userId === user.id) {
          await pending.promise;
        } else {
          const promise = (async () => {
            await chatClient.disconnectUser().catch(() => undefined);
            await chatClient.connectUser(
              { id: user.id, name: user.name, image: user.image },
              () => tokenRef.current()
            );
          })();
          connectRef.current = { userId: user.id, promise };
          await promise;
        }
      }
      if (active) {
        setClient(chatClient);
        setChannel(meetingChannel);
      }
    };

    connect().catch((cause) => {
      console.error("[CallChat] Could not open the meeting chat", cause);
      if (active) setError("Chat is unavailable right now.");
    });

    return () => {
      active = false;
      setClient(undefined);
      setChannel(undefined);
      teardownRef.current = setTimeout(() => {
        teardownRef.current = null;
        const pending = connectRef.current;
        void (async () => {
          await pending?.promise.catch(() => undefined);
          await meetingChannel.stopWatching().catch(() => undefined);
          await chatClient.disconnectUser().catch(() => undefined);
          connectRef.current = null;
        })();
      }, 250);
    };
  }, [meetingId, user.id, user.name, user.image]);

  if (!CHAT_API_KEY) {
    return (
      <ChatShell>
        <ChatNotice text="Chat is not configured for this deployment." />
      </ChatShell>
    );
  }

  if (error) {
    return (
      <ChatShell>
        <ChatNotice text={error} />
      </ChatShell>
    );
  }

  return (
    <ChatShell>
      {client && channel ? (
        <Chat client={client} theme="str-chat__theme-dark">
          <Channel channel={channel}>
            <Window>
              <MessageList />
              <MessageInput focus />
            </Window>
          </Channel>
        </Chat>
      ) : (
        <div className="flex flex-1 items-center justify-center">
          <Loader2Icon className="size-5 animate-spin text-white/50" />
        </div>
      )}
    </ChatShell>
  );
};

const ChatShell = ({ children }: { children: ReactNode }) => (
  <aside className="miva-chat flex min-h-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-[#101213]">
    <header className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
      <MessagesSquareIcon className="size-4 text-[#17cf97]" />
      <h5 className="text-sm font-semibold text-white">Meeting chat</h5>
      <span className="ml-auto text-[11px] text-white/40">
        Links shared by the agent appear here
      </span>
    </header>
    <div className="flex min-h-0 flex-1 flex-col">{children}</div>
  </aside>
);

const ChatNotice = ({ text }: { text: string }) => (
  <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-white/50">
    {text}
  </div>
);

export default CallChat;