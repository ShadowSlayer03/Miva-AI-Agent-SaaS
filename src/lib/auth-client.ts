"use client";

import { polarClient as polarClientPlugin } from "@polar-sh/better-auth";
import { createAuthClient } from "better-auth/react";

const polarPlugin = polarClientPlugin();

export const authClient = createAuthClient({
    plugins: [
        {
            ...polarPlugin,
            getActions:
                polarPlugin.getActions as unknown as () => Record<string, unknown>,
        },
    ],
})
