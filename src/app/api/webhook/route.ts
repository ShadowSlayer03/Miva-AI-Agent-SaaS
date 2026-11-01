import { db } from "@/db";
import { agents, meetings } from "@/db/schema";
import { inngest } from "@/inngest/client";
import generateAvatarURI from "@/lib/avatar";
import { streamChat } from "@/lib/stream-chat";
import { streamVideo } from "@/lib/stream-video";
import { getInstructions } from "@/lib/utils";
import {
  CallEndedEvent,
  CallRecordingReadyEvent,
  CallSessionParticipantLeftEvent,
  CallSessionStartedEvent,
  CallTranscriptionReadyEvent,
  MessageNewEvent,
} from "@stream-io/node-sdk";
import { and, eq, not } from "drizzle-orm";
//import { headers } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import OpenAI from "openai";

import { ChatCompletionMessageParam } from "openai/resources/index.mjs";

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
if (!OPENAI_API_KEY) {
  throw new Error("OPENAI_API_KEY environment variable is required");
}

const openaiClient = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const VISION_AGENT_URL =
  process.env.VISION_AGENT_URL ?? "http://127.0.0.1:8000";

function verifySignatureWithSDK(body: string, signature: string): boolean {
  return streamVideo.verifyWebhook(body, signature);
}


async function stopVisionAgent(meetingId: string) {
  try {
    const response = await fetch(
      `${VISION_AGENT_URL}/agent/${encodeURIComponent(meetingId)}`,
      { method: "DELETE" }
    );

    if (!response.ok) {
      console.error("[Meeting Agent] Failed to stop vision agent", {
        meetingId,
        status: response.status,
      });
    }
  } catch (error) {
    console.error("[Meeting Agent] Vision agent stop request failed", {
      meetingId,
      error,
    });
  }
}

export async function POST(req: NextRequest) {
  // const {signature,apiKey} = await headers();    // This is also valid here
  const signature = req.headers.get("x-signature");
  const apiKey = req.headers.get("x-api-key");

  if (!signature || !apiKey) {
    return NextResponse.json(
      { error: "Missing signature or apikey!" },
      { status: 400 }
    );
  }

  const body = await req.text();

  if (!verifySignatureWithSDK(body, signature)) {
    return NextResponse.json({ error: "Invalid signature!" }, { status: 401 });
  }

  let payload: unknown;

  try {
    payload = JSON.parse(body) as Record<string, unknown>;
  } catch (error) {
    return NextResponse.json({ error: "Invalid JSON: "+error }, { status: 400 });
  }

  const eventType = (payload as Record<string, unknown>)?.type;

  if (eventType === "call.session_started") {
    const event = payload as CallSessionStartedEvent;
    const meetingId = event.call.custom?.meetingId;

    if (!meetingId) {
      return NextResponse.json({ error: "Missing meetingId" }, { status: 400 });
    }

    const [existingMeeting] = await db
      .select()
      .from(meetings)
      .where(
        and(
          eq(meetings.id, meetingId),
          not(eq(meetings.status, "completed")),
          not(eq(meetings.status, "active")),
          not(eq(meetings.status, "cancelled")),
          not(eq(meetings.status, "processing"))
        )
      );

    if (!existingMeeting) {
      return NextResponse.json(
        { error: "Meeting not found!" },
        { status: 404 }
      );
    }

    await db
      .update(meetings)
      .set({
        status: "active",
        startedAt: new Date(),
      })
      .where(eq(meetings.id, existingMeeting.id));

    const [existingAgent] = await db
      .select()
      .from(agents)
      .where(eq(agents.id, existingMeeting.agentId));

    if (!existingAgent) {
      return NextResponse.json({ error: "Agent not found!" }, { status: 404 });
    }

    try {
      const response = await fetch(`${VISION_AGENT_URL}/agent/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          meeting_id: existingMeeting.id,
          agent_id: existingAgent.id,
          agent_name: existingAgent.name,
          instructions: existingAgent.instructions,
        }),
      });

      if (!response.ok) {
        const detail = await response.text();
        console.error("[Meeting Agent] Failed to start vision agent", {
          meetingId,
          status: response.status,
          detail,
        });
      } else {
        console.info("[Meeting Agent] Vision agent dispatched", {
          meetingId,
          agentId: existingAgent.id,
        });
      }
    } catch (error) {
      // Do not fail the webhook: Stream would retry and create duplicate
      // sessions. The meeting simply proceeds without the AI participant.
      console.error("[Meeting Agent] Vision agent service unreachable", {
        meetingId,
        error,
      });
    }
  } else if (eventType === "call.session_participant_left") {
    const event = payload as CallSessionParticipantLeftEvent;
    const meetingId = event.call_cid.split(":")[1];
    const leftUserId = event.participant?.user?.id;

    const [existingMeeting] = await db
      .select({
        id: meetings.id,
        userId: meetings.userId,
        agentId: meetings.agentId,
        status: meetings.status,
      })
      .from(meetings)
      .where(eq(meetings.id, meetingId));

    if (!existingMeeting || !leftUserId) {
      return NextResponse.json({ status: "ignored" });
    }

    // The AI agent is a participant as well. Its departure must never end the
    // human meeting — this was the bug in the old connectOpenAi handler.
    if (leftUserId === existingMeeting.agentId) {
      return NextResponse.json({ status: "ignored" });
    }

    // Only the meeting owner can close the meeting.
    const ownerLeft =
      leftUserId === existingMeeting.userId &&
      (existingMeeting.status === "active" ||
        existingMeeting.status === "upcoming");

    if (!ownerLeft) {
      return NextResponse.json({ status: "ignored" });
    }

    // Do NOT end the call here just because the owner left. A page reload, a
    // Fast Refresh remount, a sleeping laptop or a dropped connection all
    // arrive as the same event, and ending the call made the meeting die (and
    // the SFU answer "call not found") moments after it had started.
    //
    // The vision agent is the participant that keeps the call alive, and it
    // closes itself once it has been alone for AGENT_IDLE_TIMEOUT_SECONDS.
    // When the last participant leaves, Stream ends the call by itself and
    // `call.session_ended` moves the meeting to "processing". That gives the
    // owner a grace period to rejoin instead of killing the meeting.
    const call = streamVideo.video.call("default", meetingId);

    try {
      const response = await call.get();
      const participantIds =
        response.call.session?.participants.map(
          (participant) => participant.user.id
        ) ?? [];

      console.info("[Meeting Agent] Owner left the call", {
        meetingId,
        agentInCall: participantIds.includes(existingMeeting.agentId),
        othersInCall: participantIds.filter(
          (id) =>
            id !== existingMeeting.agentId && id !== existingMeeting.userId
        ).length,
      });
    } catch (error) {
      console.info("[Meeting Agent] Call already ended", {
        meetingId,
        error: error instanceof Error ? error.message : error,
      });
      return NextResponse.json({ status: "call-already-ended" });
    }

    return NextResponse.json({ status: "kept-open" });
  } else if (eventType === "call.session_ended") {
    const event = payload as CallEndedEvent;
    const meetingId = event.call.custom?.meetingId;

    if (!meetingId) {
      return NextResponse.json({ error: "Missing meetingId" }, { status: 400 });
    }

    await db
      .update(meetings)
      .set({ status: "processing", endedAt: new Date() })
      .where(and(eq(meetings.id, meetingId), eq(meetings.status, "active")));

    await stopVisionAgent(meetingId);
  } else if (eventType === "call.transcription_ready") {
    const event = payload as CallTranscriptionReadyEvent;
    const meetingId = event.call_cid.split(":")[1];

    const [updatedMeeting] = await db
      .update(meetings)
      .set({
        transcriptUrl: event.call_transcription.url,
      })
      .where(eq(meetings.id, meetingId))
      .returning();

    if (!updatedMeeting) {
      return NextResponse.json({ error: "Meeting not found" }, { status: 404 });
    }

    await inngest.send({
      name: "meetings/processing",
      data: {
        meetingId: updatedMeeting.id,
        transcriptUrl: updatedMeeting.transcriptUrl,
      },
    });
  } else if (eventType === "call.recording_ready") {
    const event = payload as CallRecordingReadyEvent;
    const meetingId = event.call_cid.split(":")[1];

    await db
      .update(meetings)
      .set({
        recordingUrl: event.call_recording.url,
      })
      .where(eq(meetings.id, meetingId));
  } else if (eventType === "message.new") {
    const event = payload as MessageNewEvent;

    const userId = event.user?.id;
    const channelId = event.channel_id;
    const text = event.message?.text;

    if (!userId || !channelId || !text) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 })
    }

    const [existingMeeting] = await db.select().from(meetings).where(and(eq(meetings.id, channelId), eq(meetings.status, "completed")))

    if (!existingMeeting) {
      return NextResponse.json({ error: "Meeting not found" }, { status: 404 })
    }

    const [existingAgent] = await db.select().from(agents).where(eq(agents.id, existingMeeting.agentId))

    if (!existingAgent) {
      return NextResponse.json({ error: "Agent not found" }, { status: 404 })
    }

    if (userId !== existingAgent.id) {
      const agentInstructions = getInstructions(existingMeeting, existingAgent);

      const channel = streamChat.channel("messaging", channelId);
      await channel.watch();

      const previousMessages = channel.state.messages.slice(-5).filter((msg) => msg.text && msg.text.trim() !== "")
        .map<ChatCompletionMessageParam>((message) => ({
          role: message.user?.id === existingAgent.id ? "assistant" : "user",
          content: message.text || ""
        }))

      const GPTResponse = await openaiClient.chat.completions.create({
        messages: [
          { role: "system", content: agentInstructions },
          ...previousMessages,
          { role: "user", content: text }
        ],
        model: "gpt-4o"
      });

      const GPTResponseText = GPTResponse.choices[0].message.content;

      if (!GPTResponseText) {
        return NextResponse.json({ error: "No response from GPT!" }, { status: 400 })
      }

      const avatarUrl = generateAvatarURI({
        seed: existingAgent.name,
        variant: "botttsNeutral"
      })

      streamChat.upsertUser({
        id: existingAgent.id,
        name: existingAgent.name,
        image: avatarUrl
      })

      channel.sendMessage({
        text: GPTResponseText,
        user: {
          id: existingAgent.id,
          name: existingAgent.name,
          image: avatarUrl
        }
      })
    }
  }

  return NextResponse.json({ status: "ok" });
}
