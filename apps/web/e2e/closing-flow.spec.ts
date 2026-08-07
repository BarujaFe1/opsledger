import { expect, test } from "@playwright/test";

/**
 * Ingestão (demo) → exceções (issues) → relatório de fechamento.
 */
test("monthly closing demo: ingest → issues → report", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  await page.getByTestId("cta-run-demo").click();
  await expect(page).toHaveURL(/\/wizard\?mode=demo/);

  await expect(page.getByTestId("goto-dashboard")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText(/Demo de fechamento carregada|Importação concluída/)).toBeVisible();

  await page.getByTestId("goto-dashboard").click();
  await expect(page).toHaveURL(/\/batches\/\d+/);
  await expect(page.getByRole("heading", { name: /Fechamento operacional/i })).toBeVisible();
  await expect(page.getByText(/Valor em divergência/i)).toBeVisible();

  await page.getByTestId("link-issues").click();
  await expect(page).toHaveURL(/\/batches\/\d+\/issues/);
  await expect(page.getByRole("heading", { name: /Divergências/i })).toBeVisible();

  await page.goto(page.url().replace(/\/issues$/, ""));
  await page.getByTestId("btn-report").click();
  await expect(page.getByTestId("executive-report")).toBeVisible();
  await expect(page.getByText(/Relatório executivo/i)).toBeVisible();
  await expect(page.locator("[data-testid=executive-report]")).toContainText(/Batch|Issues|OpsLedger|fechamento/i);
});
