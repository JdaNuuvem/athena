import type { NextConfig } from "next";

// ponytail: em producao (standalone Docker), o backend Python hermes-agent roda
// como container irmao no Coolify. Containers no mesmo projeto se alcançam pelo
// UUID do recurso. O service ID do hermes-agent eh w9hn3qezdgivens9g1o7r3of.
// Em dev local, usa 127.0.0.1:3000 (Flask direto).
const API_TARGET = process.env.ATHENA_API_URL || (
  process.env.NODE_ENV === "production"
    ? "http://w9hn3qezdgivens9g1o7r3of:3000"
    : "http://127.0.0.1:3000"
);

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
