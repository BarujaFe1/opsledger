import { expect, test } from "@playwright/test";

/**
 * Critical path: home → demo ingest → dashboard → issues → open an issue → back → report.
 *
 * Runs against the SAME public-demo contract used in production. When the API is started
 * with PUBLIC_DEMO_MODE=1 (CI E2E job), the demo returns the sentinel batch id -1, so this
 * test exercises the exact path that previously broke with "ID de batch inválido." The hard
 * regression guard (no "ID de batch inválido" + dashboard loaded) applies in every mode.
 */
test("monthly closing demo: ingest → dashboard → issues → issue → report", async ({ page }) => {
  const expectPublicDemo = process.env.PUBLIC_DEMO_MODE === "1";

  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  await page.getByTestId("cta-run-demo").click();
  await expect(page).toHaveURL(/\/wizard\?mode=demo/);

  await expect(page.getByTestId("goto-dashboard")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText(/Demo de fechamento carregada|Importação concluída/)).toBeVisible();

  await page.getByTestId("goto-dashboard").click();

  // Regression guard: navigation must land on a valid batch route and never show the
  // "ID de batch inválido" error that the demo sentinel (-1) used to trigger.
  if (expectPublicDemo) {
    await expect(page).toHaveURL(/\/batches\/-1(\/|$)/);
  } else {
    await expect(page).toHaveURL(/\/batches\/\d+/);
  }
  await expect(page.getByText(/ID de batch inválido/i)).toHaveCount(0);

  await expect(page.getByRole("heading", { name: /Fechamento operacional/i })).toBeVisible();
  await expect(page.getByText(/Valor em divergência/i)).toBeVisible();

  // Fase 2b.1: cash-realization KPIs (refund/chargeback dimension) must render
  // alongside the payment-matching KPIs and must NOT reduce reconciled/under.
  // `.first()` disambiguates each KPI label from the explanatory helper paragraph
  // (rendered later in the DOM) which repeats the same terms.
  await expect(page.getByText(/Recebido bruto/i).first()).toBeVisible();
  await expect(page.getByText(/Reembolsado/i).first()).toBeVisible();
  await expect(page.getByText(/Chargeback \(exposição em disputa\)/i).first()).toBeVisible();
  await expect(page.getByText(/Caixa líquido/i).first()).toBeVisible();

  // Issues register
  await page.getByTestId("link-issues").click();
  await expect(page).toHaveURL(/\/batches\/-?\d+\/issues/);
  await expect(page.getByRole("heading", { name: /Divergências/i })).toBeVisible();

  // Open the first issue and confirm the detail view renders
  await page.locator("table tbody tr").first().getByRole("link").first().click();
  await expect(page).toHaveURL(/\/issues\/\d+/);
  await expect(page.getByRole("link", { name: /← Issues Register/i })).toBeVisible();
  await expect(page.getByText(/Ação recomendada/i)).toBeVisible();

  // Back to the issues register, then to the dashboard
  await page.getByRole("link", { name: /← Issues Register/i }).click();
  await expect(page).toHaveURL(/\/batches\/-?\d+\/issues/);
  await expect(page.getByRole("heading", { name: /Divergências/i })).toBeVisible();

  await page.getByRole("link", { name: /← Dashboard/i }).click();
  await expect(page).toHaveURL(/\/batches\/-?\d+/);

  // Executive report
  await page.getByTestId("btn-report").click();
  await expect(page.getByTestId("executive-report")).toBeVisible();
  await expect(page.getByText(/Relatório executivo/i)).toBeVisible();
  await expect(page.locator("[data-testid=executive-report]")).toContainText(/Batch|Issues|OpsLedger|fechamento/i);

  // Fase 2b.1: the executive report must surface the cash-realization section.
  await expect(page.locator("[data-testid=executive-report]")).toContainText(/Realização de caixa/i);
  await expect(page.locator("[data-testid=executive-report]")).toContainText(/Reembolsado/i);
});
