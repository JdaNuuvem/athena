import { test, expect } from "@playwright/test";

// Golden path do cadastro empresarial de lojas (Fase 2). Precisa de
// E2E_ADMIN_EMAIL / E2E_ADMIN_PW apontando pra um usuario admin real do
// ambiente local (ver ATHENA_ADMIN_EMAIL/ATHENA_ADMIN_PW do backend) — sem
// credencial hardcoded no teste.
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "";
const ADMIN_PW = process.env.E2E_ADMIN_PW || "";

test.beforeEach(async () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PW, "E2E_ADMIN_EMAIL/E2E_ADMIN_PW nao configurados — pulei o teste E2E");
});

test("cria loja, edita cadastro completo e confirma persistencia", async ({ page }) => {
  const nomeLoja = `E2E Loja ${Date.now()}`;

  await page.goto("/login");
  await page.fill("#email", ADMIN_EMAIL);
  await page.fill("#password", ADMIN_PW);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(/\/dashboard/);

  // Cria loja rapida
  await page.goto("/lojas");
  await page.getByRole("button", { name: "+ Nova Loja" }).click();
  await page.getByPlaceholder("Nome da loja").fill(nomeLoja);
  await page.getByRole("button", { name: "Salvar" }).click();
  await expect(page.getByText(nomeLoja)).toBeVisible();

  // Abre detalhe
  const card = page.locator("div", { hasText: nomeLoja }).last();
  await card.getByRole("link", { name: /Ver detalhes/ }).click();
  await page.waitForURL(/\/lojas\/\d+/);

  // Aba Geral — preenche nome fantasia e salva
  const nomeFantasiaInput = page.locator("label:has-text('Nome fantasia') + input");
  await nomeFantasiaInput.fill("Charme Nilópolis E2E");
  await page.getByRole("button", { name: "Salvar" }).first().click();
  await expect(page.getByText("Salvo!").first()).toBeVisible();

  // Reload e confirma persistencia
  await page.reload();
  await expect(nomeFantasiaInput).toHaveValue("Charme Nilópolis E2E");

  // Aba Midia — upload de uma imagem fake
  await page.getByRole("button", { name: "Mídia" }).click();
  const fileInput = page.locator('input[type="file"]').first();
  await fileInput.setInputFiles({
    name: "logo-teste.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      "base64"
    ),
  });
  await expect(page.getByText("Enviando...")).toBeHidden({ timeout: 10_000 });
  await expect(page.locator("img[alt='logo-teste.png']")).toBeVisible();
});
