import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["172.20.0.190"],
  async rewrites() {
    return [
      // Serve the chat workspace at "/" without an HTTP redirect.
      { source: "/", destination: "/chat" },
    ];
  },
};

export default nextConfig;
