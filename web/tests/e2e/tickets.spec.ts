import { test, expect } from "@playwright/test";

// Golden path de tickets estruturados. Precisa de E2E_ADMIN_EMAIL/E2E_ADMIN_PW
// apontando pra um usuario admin real do ambiente local — mesmo padrao de
// web/tests/e2e/lojas.spec.ts, sem credencial hardcoded no teste.
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || "";
const ADMIN_PW = process.env.E2E_ADMIN_PW || "";

test.beforeEach(async () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PW, "E2E_ADMIN_EMAIL/E2E_ADMIN_PW nao configurados — pulei o teste E2E");
});

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.fill("#email", ADMIN_EMAIL);
  await page.fill("#password", ADMIN_PW);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL(/\/dashboard/);
}

// Cria um ticket a partir da listagem e retorna o Locator da linha da
// tabela correspondente. A listagem ordena por id DESC (mais recente
// primeiro), entao nao da pra assumir posicao fixa (.first()/.last()) —
// filtramos pelo nome de cliente unico (timestamp), mesmo principio do
// `card` filtrado por hasText em lojas.spec.ts.
async function criarTicket(page: import("@playwright/test").Page, cliente: string, assunto: string) {
  await page.goto("/atendimento/tickets");
  await page.getByRole("button", { name: "+ Novo Ticket" }).click();
  await page.getByPlaceholder("Nome do cliente").fill(cliente);
  await page.getByPlaceholder("Assunto").fill(assunto);
  await page.getByRole("button", { name: "Criar Ticket" }).click();
  await expect(page.getByText(cliente)).toBeVisible();

  const linha = page.locator("tr", { hasText: cliente });
  await linha.getByRole("link", { name: /#\d+/ }).click();
  await page.waitForURL(/\/atendimento\/tickets\/\d+/);
}

test("cria ticket, atribui, muda status, envia mensagem e fecha", async ({ page }) => {
  const cliente = `E2E Cliente ${Date.now()}`;

  await login(page);
  await criarTicket(page, cliente, "Duvida sobre pedido E2E");

  await expect(page.getByText("Duvida sobre pedido E2E")).toBeVisible();

  // Atribui a si mesmo (primeiro atendente disponivel no select)
  const selectAtendente = page.locator("select").filter({ hasText: "Não atribuído" });
  await selectAtendente.selectOption({ index: 1 });

  // Muda status para pendente
  await page.getByRole("button", { name: "Marcar pendente" }).click();
  await expect(page.getByText("pendente")).toBeVisible();

  // Envia mensagem
  await page.getByPlaceholder("Digite sua mensagem...").fill("Mensagem de teste E2E");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText("Mensagem de teste E2E")).toBeVisible();

  // Fecha o ticket
  await page.getByRole("button", { name: "Fechar" }).click();
  await expect(page.getByText("fechado")).toBeVisible();

  // Volta pra listagem, confirma que aparece na tab Fechado
  await page.getByRole("link", { name: "Tickets" }).click();
  await page.getByRole("button", { name: "Fechado" }).click();
  await expect(page.getByText(cliente)).toBeVisible();
});

test("mudanca de status via WebSocket aparece em outra aba sem F5", async ({ browser }) => {
  const context = await browser.newContext();
  const pageA = await context.newPage();
  const pageB = await context.newPage();

  await login(pageA);
  await login(pageB);

  const cliente = `E2E WS ${Date.now()}`;
  await criarTicket(pageA, cliente, "Teste WS");
  const url = pageA.url();

  await pageB.goto(url);
  await expect(pageB.getByText("aberto")).toBeVisible();

  await pageA.getByRole("button", { name: "Marcar pendente" }).click();
  await expect(pageB.getByText("pendente")).toBeVisible({ timeout: 10_000 });

  await context.close();
});
