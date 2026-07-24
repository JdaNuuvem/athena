import type { NextConfig } from "next";

// ponytail: backend Python (hermes_agents) é o primário — tem 335+ endpoints
// vs 57 do TS. Roteia /api/* para ele por padrão. Em dev, ATHENA_API_URL pode
// sobrescrever (ex: Coolify). Porta 3000 = Flask (docker/production/Dockerfile).
const API_TARGET = process.env.ATHENA_API_URL || "http://127.0.0.1:3000";

// ponytail: producao serve um export estatico (hermes_agents/dashboard/) direto
// pelo Flask — nao ha servidor Node.js rodando, entao rewrites() nao se aplica
// la (mesma origem, fetch("/api/...") ja bate no Flask sem proxy). rewrites()
// so' e' necessario em `next dev` (server Next + Flask em portas separadas).
// NEXT_STATIC_EXPORT=true ativa o modo de export usado para gerar esse build.
const isStaticExport = process.env.NEXT_STATIC_EXPORT === "true";

const nextConfig: NextConfig = isStaticExport
  ? { output: "export" }
  : {
      output: "standalone",
      async rewrites() {
        return [
          { source: "/api/:path*", destination: `${API_TARGET}/api/:path*` },
          { source: "/webhook/:path*", destination: `${API_TARGET}/webhook/:path*` },
        ];
      },
    };

export default nextConfig;
