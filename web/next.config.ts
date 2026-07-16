import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:3001/api/:path*" },
      { source: "/api/bling/auth/callback", destination: "http://127.0.0.1:3001/api/bling/auth/callback" },
    ];
  },
};

export default nextConfig;
