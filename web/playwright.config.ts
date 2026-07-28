import { defineConfig } from "@playwright/test";

// Testes E2E do cadastro de lojas (Fase 2). Backend Flask + Postgres e o
// Next dev server precisam estar rodando ANTES de `npm run test:e2e` —
// este config nao sobe o Flask automaticamente porque ele depende de um
// Postgres ja populado (nao da pra improvisar isso aqui). Ajuste
// E2E_BASE_URL se o Next dev estiver em outra porta.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3010",
    trace: "on-first-retry",
  },
});
