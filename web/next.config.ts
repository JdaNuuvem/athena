import type { NextConfig } from "next";

// ponytail: backend Python (hermes_agents) é o primário — tem 335+ endpoints
// vs 57 do TS. Roteia /api/* para ele por padrão. Em dev, ATHENA_API_URL pode
// sobrescrever (ex: Coolify). Porta 3000 = Flask (docker/production/Dockerfile).
const API_TARGET = process.env.ATHENA_API_URL || "http://127.0.0.1:3000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_TARGET}/api/:path*` },
      { source: "/webhook/:path*", destination: `${API_TARGET}/webhook/:path*` },
    ];
  },
};

export default nextConfig;
