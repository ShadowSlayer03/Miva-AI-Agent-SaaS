/* eslint-disable @typescript-eslint/no-explicit-any */

import { db } from "@/db";
import { agents, meetings } from "@/db/schema";
import { polarClient } from "@/lib/polar";
import { createTRPCRouter, protectedProcedure } from "@/trpc/init";
import { count, eq } from "drizzle-orm";

export const premiumRouter = createTRPCRouter({
    getCurrentSubscription: protectedProcedure.query(async({ctx})=>{
        const customer = await polarClient.customers.getStateExternal(
            ctx.auth.user.id
        )

        const subscription = customer.active_subscriptions?.[0];

        if(!subscription) return null;

        const product = await polarClient.products.get(
            subscription.product_id
        )

        return product;
    }),
    getProducts: protectedProcedure.query(async () => {
        const products = await polarClient.products.list({
            is_archived: false,
            is_recurring: true,
            sorting: ["price_amount"]
        })

        return products.items;
    }),
    getFreeUsage: protectedProcedure.query(async ({ ctx }) => {
        try {
            try {
                await polarClient.customers.getStateExternal(ctx.auth.user.id);
            } catch (err: any) {
                if (err?.error === "ResourceNotFound") {
                    // Automatically create a Polar customer for free tier users
                    await polarClient.customers.create({
                        external_id: ctx.auth.user.id,
                        name: ctx.auth.user.name ?? "User",
                        email: ctx.auth.user.email ?? "user@example.com",
                    });
                } else {
                    throw err;
                }
            }

            // Always fetch usage
            const [userMeetings] = await db.select({
                count: count(meetings.id)
            }).from(meetings).where(eq(meetings.userId, ctx.auth.user.id));

            const [userAgents] = await db.select({
                count: count(agents.id)
            }).from(agents).where(eq(agents.userId, ctx.auth.user.id));

            return {
                meetingCount: userMeetings?.count ?? 0,
                agentCount: userAgents?.count ?? 0,
            };
        } catch (err) {
            console.error("Free usage error:", err);
            throw new Error("Failed to fetch free usage data");
        }
    })


})