import { db } from "@/db";
import { agents, meetings, user } from "@/db/schema";
import { createTRPCRouter, premiumProcedure, protectedProcedure } from "@/trpc/init";
import { z } from "zod";
import {
  and,
  count,
  desc,
  eq,
  getTableColumns,
  ilike,
  inArray,
  sql,
} from "drizzle-orm";
import {
  DEFAULT_PAGE,
  DEFAULT_PAGE_SIZE,
  MAX_PAGE_SIZE,
  MIN_PAGE_SIZE,
} from "@/constants";
import { TRPCError } from "@trpc/server";
import { meetingsInsertSchema, meetingsUpdateSchema } from "../schemas";
import { MeetingStatus, StreamTranscriptItem } from "../types";
import { streamVideo } from "@/lib/stream-video";
import generateAvatarURI from "@/lib/avatar";
import JSONL from "jsonl-parse-stringify";
import { streamChat } from "@/lib/stream-chat";
import { stopVisionAgent } from "@/lib/vision-agent";

export const meetingsRouter = createTRPCRouter({
  generateChatToken: protectedProcedure.mutation(async ({ ctx }) => {
    const token = streamChat.createToken(ctx.auth.user.id);
    await streamChat.upsertUser({
      id: ctx.auth.user.id,
      role: "admin",
    });

    return token;
  }),
  getTranscript: protectedProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input, ctx }) => {
      const [existingMeeting] = await db
        .select()
        .from(meetings)
        .where(
          and(eq(meetings.id, input.id), eq(meetings.userId, ctx.auth.user.id))
        );

      if (!existingMeeting) {
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Meeting Not Found!",
        });
      }

      if (!existingMeeting.transcriptUrl) {
        return [];
      }

      const transcript = await fetch(existingMeeting.transcriptUrl)
        .then((res) => res.text())
        .then((text) => JSONL.parse<StreamTranscriptItem>(text))
        .catch(() => {
          return [];
        });

      const speakerIds = [
        ...new Set(transcript.map((item) => item.speaker_id)),
      ];

      const userSpeakers = await db
        .select()
        .from(user)
        .where(inArray(user.id, speakerIds))
        .then((users) =>
          users.map((user) => ({
            ...user,
            image:
              user.image ??
              generateAvatarURI({ seed: user.name, variant: "initials" }),
          }))
        );

      const agentSpeakers = await db
        .select()
        .from(agents)
        .where(inArray(agents.id, speakerIds))
        .then((agents) =>
          agents.map((agent) => ({
            ...agent,
            image:
              generateAvatarURI({ seed: agent.name, variant: "botttsNeutral" }),
          }))
        );

      const speakers = [...userSpeakers, ...agentSpeakers];

      const transcriptWithSpeakers = transcript.map((item) => {
        const speaker = speakers.find(
          (speaker) => speaker.id === item.speaker_id
        );

        if (!speaker) {
          return {
            ...item,
            user: {
              name: "Unknown",
              image: generateAvatarURI({
                seed: "Unknown",
                variant: "initials",
              }),
            },
          };
        }

        return {
          ...item,
          user: {
            name: speaker.name,
            image: speaker.image,
          },
        };
      });
      return transcriptWithSpeakers;
    }),
  generateToken: protectedProcedure.mutation(async ({ ctx }) => {
    await streamVideo.upsertUsers([
      {
        id: ctx.auth.user.id,
        name: ctx.auth.user.name,
        image:
          ctx.auth.user.image ??
          generateAvatarURI({ seed: ctx.auth.user.name, variant: "initials" }),
      },
    ]);

    const expirationTime = Math.floor(Date.now() / 1000) + 3600;

    const token = streamVideo.generateUserToken({
      user_id: ctx.auth.user.id,
      exp: expirationTime,
      validity_in_seconds: 3600, // 1 hour validity
    });

    return token;
  }),
  update: protectedProcedure
    .input(meetingsUpdateSchema)
    .mutation(async ({ ctx, input }) => {
      const [updatedMeeting] = await db
        .update(meetings)
        .set(input)
        .where(
          and(eq(meetings.id, input.id), eq(meetings.userId, ctx.auth.user.id))
        )
        .returning();

      if (!updatedMeeting)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Meeting Not Found!",
        });

      return updatedMeeting;
    }),
  remove: protectedProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ ctx, input }) => {
      const [removedMeeting] = await db
        .delete(meetings)
        .where(
          and(eq(meetings.id, input.id), eq(meetings.userId, ctx.auth.user.id))
        )
        .returning();

      if (!removedMeeting)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Meeting Not Found!",
        });

      return removedMeeting;
    }),
  create: premiumProcedure("meetings")
    .input(meetingsInsertSchema)
    .mutation(async ({ input, ctx }) => {
      const { auth } = ctx;

      const [createdMeeting] = await db
        .insert(meetings)
        .values({
          ...input,
          userId: auth.user.id,
        })
        .returning();

      const call = streamVideo.video.call("default", createdMeeting.id);
      await call.create({
        data: {
          created_by_id: ctx.auth.user.id,
          custom: {
            meetingId: createdMeeting.id,
            meetingName: createdMeeting.name,
          },
          settings_override: {
            transcription: {
              language: "en",
              mode: "auto-on",
              closed_caption_mode: "auto-on",
            },
            recording: {
              mode: "auto-on",
              quality: "1080p",
              layout: { name: "spotlight" },
            },
          },
        },
      });

      const [existingAgent] = await db
        .select()
        .from(agents)
        .where(eq(agents.id, createdMeeting.agentId));

      if (!existingAgent) {
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Agent not found",
        });
      }

      // To sync the agent with Stream and recognise it as a participant
      // Agent will be authenticated using stream token with proper id, name, role and avatar.
      // To be searchable and available for call invites, recordings, captions etc.
      await streamVideo.upsertUsers([
        {
          id: existingAgent.id,
          name: existingAgent.name,
          role: "user",
          image: generateAvatarURI({
            seed: existingAgent.name,
            variant: "botttsNeutral",
          }),
        },
      ]);

      return createdMeeting;
    }),
  endForAll: protectedProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ ctx, input }) => {
      const [existingMeeting] = await db
        .select({ id: meetings.id, status: meetings.status })
        .from(meetings)
        .where(
          and(eq(meetings.id, input.id), eq(meetings.userId, ctx.auth.user.id))
        );

      if (!existingMeeting) {
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Meeting Not Found!",
        });
      }

      // Disconnect every participant at once. If the call already ended this
      // throws, but the meeting state still has to move forward.
      try {
        await streamVideo.video.call("default", existingMeeting.id).end();
      } catch (error) {
        console.error("[meetings.endForAll] Failed to end call", error);
      }

      if (
        existingMeeting.status === "active" ||
        existingMeeting.status === "upcoming"
      ) {
        await db
          .update(meetings)
          .set({ status: "processing", endedAt: new Date() })
          .where(eq(meetings.id, existingMeeting.id));
      }

      // Normally `call.session_ended` does this. Doing it here as well makes
      // the button work even when webhook delivery is delayed or broken.
      await stopVisionAgent(existingMeeting.id);

      return { id: existingMeeting.id };
    }),
  getForCall: protectedProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input, ctx }) => {
      const [existingMeeting] = await db
        .select({
          id: meetings.id,
          name: meetings.name,
          status: meetings.status,
          agentId: meetings.agentId,
          userId: meetings.userId,
          startedAt: meetings.startedAt,
          endedAt: meetings.endedAt,
        })
        .from(meetings)
        .innerJoin(agents, eq(meetings.agentId, agents.id))
        .where(eq(meetings.id, input.id));

      if (!existingMeeting)
        throw new TRPCError({
          code: "NOT_FOUND",
          message: "Meeting Not Found!",
        });


      const isJoinable =
        existingMeeting.endedAt === null &&
        (existingMeeting.status === "upcoming" ||
          existingMeeting.status === "active");

      const { userId, ...meeting } = existingMeeting;

      return {
        ...meeting,
        isJoinable,
        isOwner: userId === ctx.auth.user.id,
      };
    }),
  getOne: protectedProcedure
  .input(z.object({ id: z.string() }))
  .query(async ({ input, ctx }) => {
    const [existingMeeting] = await db
      .select({
        ...getTableColumns(meetings),
        agent: agents,
        duration: sql<number>`EXTRACT(EPOCH FROM (ended_at - started_at))`.as("duration"),
        meetingCount: sql<number>`(SELECT COUNT(*) FROM meetings WHERE agent_id = ${meetings.agentId})`,
      })
      .from(meetings)
      .innerJoin(agents, eq(meetings.agentId, agents.id))
      .where(and(eq(meetings.id, input.id), eq(meetings.userId, ctx.auth.user.id)));

    if (!existingMeeting)
      throw new TRPCError({
        code: "NOT_FOUND",
        message: "Meeting Not Found!",
      });

    return existingMeeting;
  }),
  getMany: protectedProcedure
    .input(
      z.object({
        page: z.number().default(DEFAULT_PAGE),
        pageSize: z
          .number()
          .min(MIN_PAGE_SIZE)
          .max(MAX_PAGE_SIZE)
          .default(DEFAULT_PAGE_SIZE),
        search: z.string().nullish(),
        agentId: z.string().nullish(),
        status: z
          .enum(
            Object.values(MeetingStatus) as [MeetingStatus, ...MeetingStatus[]]
          )
          .nullish(),
      })
    )
    .query(async ({ input, ctx }) => {
      const { search, page, pageSize, status, agentId } = input;

      const whereClause = [
        eq(meetings.userId, ctx.auth.user.id),
        search ? ilike(meetings.name, `%${search}%`) : undefined,
        status ? eq(meetings.status, status) : undefined,
        agentId ? eq(meetings.agentId, agentId) : undefined,
      ].filter(Boolean);

      const data = await db
        .select({
          ...getTableColumns(meetings),
          agent: agents,
          duration: sql<number>`EXTRACT(EPOCH FROM (ended_at - started_at))`.as(
            "duration"
          ),
          meetingCount: sql`(SELECT COUNT(*) FROM meetings WHERE agent_id = ${meetings.agentId})`.as("meetingCount"),
        })
        .from(meetings)
        .innerJoin(agents, eq(meetings.agentId, agents.id))
        .where(and(...whereClause))
        .orderBy(desc(meetings.createdAt), desc(meetings.id))
        .limit(pageSize)
        .offset((page - 1) * pageSize);

      const [total] = await db
        .select({ count: count() })
        .from(meetings)
        .innerJoin(agents, eq(meetings.agentId, agents.id))
        .where(and(...whereClause));

      return {
        items: data,
        total: total.count,
        totalPages: Math.ceil(total.count / pageSize),
      };
    }),
});
