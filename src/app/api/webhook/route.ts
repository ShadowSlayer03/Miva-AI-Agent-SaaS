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

function verifySignatureWithSDK(body: string, signature: string): boolean {
  return streamVideo.verifyWebhook(body, signature);
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

    const call = streamVideo.video.call("default", meetingId);
    const realtimeModel = process.env.OPENAI_REALTIME_MODEL || undefined;

    const realtimeClient = await streamVideo.video.connectOpenAi({
      call,
      openAiApiKey: OPENAI_API_KEY!,
      agentUserId: existingAgent.id,
      model: realtimeModel,
    });

    const agentName = existingAgent.name;
    const liveInstructions = `
      You are ${agentName}, an AI voice assistant inside a live multi-participant meeting.
      You only participate when you are directly addressed. Specifically:
      - Listen to the entire conversation and do not respond to statements that are not directed at you.
      - Speak only when someone calls you by your name (${agentName}) or explicitly asks for your opinion, answer, or help.
      - Never interrupt people, never answer on someone else's behalf, and never comment on side conversations.
      - When you do speak, ground your answer in the conversation so far, use earlier context to stay coherent, and answer concisely.
      - If a request is ambiguous, ask a short clarifying question before answering.

      As your base behavior, keep following these instructions:
      ${existingAgent.instructions}
    `;

    type RealtimeSessionUpdate = Parameters<
      typeof realtimeClient.updateSession
    >[0];

    const sessionUpdate: RealtimeSessionUpdate = {
      instructions: liveInstructions,
    };

    const semanticVadModels = new Set([
      "gpt-4o-realtime-preview-2025-06-03",
      "gpt-realtime",
      "gpt-realtime-mini",
    ]);

    const turnDetection = process.env.REALTIME_TURN_DETECTION;
    const supportsSemanticVad =
      realtimeModel !== undefined && semanticVadModels.has(realtimeModel);

    if (turnDetection === "semantic_vad" && supportsSemanticVad) {
      (
        sessionUpdate as RealtimeSessionUpdate & {
          turn_detection: { type: "semantic_vad" };
        }
      ).turn_detection = { type: "semantic_vad" };
    } else if (turnDetection === "semantic_vad") {
      console.warn(
        `Semantic VAD requested for unsupported realtime model "${realtimeModel ?? "(default)"}", falling back to instructions-only wake-word gating`
      );
    }

    realtimeClient.updateSession(sessionUpdate);
  } else if (eventType === "call.session_participant_left") {
    const event = payload as CallSessionParticipantLeftEvent;
    const meetingId = event.call_cid.split(":")[1];

    if (!meetingId) {
      return NextResponse.json({ error: "Missing meetingId" }, { status: 400 });
    }

    const call = streamVideo.video.call("default", meetingId);
    await call.end();
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
