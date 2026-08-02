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

// PainelControle.tsx renderiza tanto o badge de status (<span>aberto|pendente|
// fechado</span>) quanto linhas de metadado tipo "Aberto em: ..."/"Fechado
// em: ..." (<p>) — que colidem com getByText() simples (substring,
// case-insensitive) e disparam strict-mode violation (2+ elementos). Isso foi
// reproduzido de verdade: "Aberto em:" existe pra TODO ticket, entao
// getByText("aberto") quebra 100% das vezes. Escopamos ao <span> do badge com
// regex ancorada (^...$) pra nao casar com o texto mais longo dos <p> de
// metadado nem com ancestrais que acumulam texto adicional (label "Status",
// botoes de transicao etc.).
function statusBadge(page: import("@playwright/test").Page, status: string) {
  return page.locator("span", { hasText: new RegExp(`^${status}$`, "i") });
}

// Cria um ticket a partir do modal "+ Novo Ticket" na listagem e confirma que
// aparece na tabela. A listagem ordena por id DESC (mais recente primeiro),
// entao a posicao do ticket recem-criado nao e' previsivel (nao da pra supor
// .first()/.last()) — quem chama filtra por linha via `linhaDoTicket`.
async function criarTicket(page: import("@playwright/test").Page, cliente: string, assunto: string) {
  await page.goto("/atendimento/tickets");
  await page.getByRole("button", { name: "+ Novo Ticket" }).click();
  await page.getByPlaceholder("Nome do cliente").fill(cliente);
  await page.getByPlaceholder("Assunto").fill(assunto);
  await page.getByRole("button", { name: "Criar Ticket" }).click();
  await expect(page.getByText(cliente)).toBeVisible();
}

// Localiza a linha da tabela pelo nome de cliente unico (timestamp) — mesmo
// principio do `card` filtrado por hasText em lojas.spec.ts — e abre o
// detalhe pelo link do numero do ticket (#0001 etc.) dentro dessa linha.
async function abrirTicketDaListagem(page: import("@playwright/test").Page, cliente: string) {
  const linha = page.locator("tr", { hasText: cliente });
  await linha.getByRole("link", { name: /#\d+/ }).click();
  await page.waitForURL(/\/atendimento\/tickets\/\d+/);
}

test("cria ticket, atribui, muda status, envia mensagem e fecha", async ({ page }) => {
  const cliente = `E2E Cliente ${Date.now()}`;

  await login(page);
  await criarTicket(page, cliente, "Duvida sobre pedido E2E");

  // Confirma que o ticket recem-criado (status inicial "aberto") aparece na
  // tab "Aberto" da listagem, nao so na tab "Todos" (default).
  await page.getByRole("button", { name: "Aberto" }).click();
  await expect(page.getByText(cliente)).toBeVisible();

  await abrirTicketDaListagem(page, cliente);
  await expect(page.getByText("Duvida sobre pedido E2E")).toBeVisible();

  // Atribui a si mesmo (primeiro atendente disponivel no select)
  const selectAtendente = page.locator("select").filter({ hasText: "Não atribuído" });
  await selectAtendente.selectOption({ index: 1 });

  // Muda status para pendente
  await page.getByRole("button", { name: "Marcar pendente" }).click();
  await expect(statusBadge(page, "pendente")).toBeVisible();

  // Envia mensagem
  await page.getByPlaceholder("Digite sua mensagem...").fill("Mensagem de teste E2E");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText("Mensagem de teste E2E")).toBeVisible();

  // Fecha o ticket
  await page.getByRole("button", { name: "Fechar" }).click();
  await expect(statusBadge(page, "fechado")).toBeVisible();

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
  await abrirTicketDaListagem(pageA, cliente);
  const url = pageA.url();

  await pageB.goto(url);
  await expect(statusBadge(pageB, "aberto")).toBeVisible();

  await pageA.getByRole("button", { name: "Marcar pendente" }).click();
  await expect(statusBadge(pageB, "pendente")).toBeVisible({ timeout: 10_000 });

  await context.close();
});
