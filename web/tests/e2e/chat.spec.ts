import { test, expect } from "@playwright/test";

// RocketChatFrame le NEXT_PUBLIC_ROCKETCHAT_URL em tempo de build/dev do
// Next — precisa estar setada ANTES de rodar `npm run dev` (reinicie o dev
// server se a variavel mudar). Mesmo padrao de tickets.spec.ts: pula sem
// hardcodar URL de teste real no arquivo.
const ROCKETCHAT_URL = process.env.NEXT_PUBLIC_ROCKETCHAT_URL || "";

test.beforeEach(async () => {
  test.skip(!ROCKETCHAT_URL, "NEXT_PUBLIC_ROCKETCHAT_URL nao configurada — pulei o teste E2E do /chat");
});

test("mostra estado indisponivel quando o Rocket.Chat nao responde, com botao de retry", async ({ page }) => {
  await page.route(`${ROCKETCHAT_URL}/api/v1/info`, (route) => route.abort());

  await page.goto("/chat");

  await expect(page.getByText("Chat indisponível no momento.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
});

test("retry apos infra voltar troca o estado indisponivel pelo iframe", async ({ page }) => {
  let disponivel = false;
  await page.route(`${ROCKETCHAT_URL}/api/v1/info`, (route) =>
    disponivel ? route.fulfill({ status: 200, body: "{}" }) : route.abort()
  );

  await page.goto("/chat");
  await expect(page.getByText("Chat indisponível no momento.")).toBeVisible();

  disponivel = true;
  await page.getByRole("button", { name: "Tentar novamente" }).click();

  await expect(page.locator('iframe[title="Chat"]')).toHaveAttribute(
    "src",
    `${ROCKETCHAT_URL}?layout=embedded`
  );
});
