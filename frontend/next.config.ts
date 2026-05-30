import type { NextConfig } from "next";

const allowedDevOrigins = (process.env.ALLOWED_DEV_ORIGINS ?? "")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins,
  async rewrites() {
    return [
      // Serve the chat workspace at "/" without an HTTP redirect.
      { source: "/", destination: "/chat" },
    ];
  },
};

export default nextConfig;
