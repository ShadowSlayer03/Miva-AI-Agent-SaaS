import { createPolar, createPolarCore } from "@polar-sh/sdk/2026-10";

const polarOptions = {
  accessToken: process.env.POLAR_ACCESS_TOKEN ?? "",
  environment: "sandbox" as const,
};

export const polarClient = createPolar(polarOptions);
export const polarCoreClient = createPolarCore(polarOptions);