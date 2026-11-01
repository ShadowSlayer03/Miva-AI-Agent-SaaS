import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { db } from "@/db";
import * as schema from "@/db/schema";
import { polar, checkout, portal } from "@polar-sh/better-auth";

import { polarCoreClient } from "./polar";

const authHosts = [
  "localhost:3000",
  "127.0.0.1:3000",
  "mivaai.share.zrok.io",
  "miva-ai-agent.vercel.app",
];

const authOrigins = authHosts.map(
  (host) => `${host.includes("localhost") || host.startsWith("127.") ? "http" : "https"}://${host}`
);

export const auth = betterAuth({
  baseURL: {
    allowedHosts: authHosts,
    protocol: "auto",
    fallback: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  },
  trustedOrigins: authOrigins,
  advanced: {
    // zrok forwards the public host/protocol in x-forwarded-* headers; Next
    // rewrites request.url to localhost, so Better Auth must trust them.
    trustedProxyHeaders: true,
  },
  plugins: [
    polar({
      client: polarCoreClient,
      createCustomerOnSignUp: true,
      use: [
        checkout({
          authenticatedUsersOnly: true,
          successUrl: "/upgrade"
        }),
        portal()
      ]
    })
  ],
  emailAndPassword: {
    enabled: true,
  },
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID as string,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
    },
    github: {
      clientId: process.env.GITHUB_CLIENT_ID as string,
      clientSecret: process.env.GITHUB_CLIENT_SECRET as string,
    },
  },
  database: drizzleAdapter(db, {
    provider: "pg",
    schema: {
      ...schema,
    },
  }),
});
