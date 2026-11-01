import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["mivaai.share.zrok.io"],
  async redirects() {
    return [
      {
        source: "/",
        destination: "/meetings",
        permanent: true
      }
    ]
  }
};

export default nextConfig;
