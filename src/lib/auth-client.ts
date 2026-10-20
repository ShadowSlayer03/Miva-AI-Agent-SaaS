"use client";

import { polarClient as polarClientPlugin } from "@polar-sh/better-auth";
import { createAuthClient } from "better-auth/react";

const polarPlugin = polarClientPlugin();

export const authClient = createAuthClient({
    // Defaults to same-origin; override with NEXT_PUBLIC_API_BASE_URL when needed
    baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? undefined,
    plugins: [
        {
            ...polarPlugin,
            getActions:
                polarPlugin.getActions as unknown as () => Record<string, unknown>,
        },
    ],
})