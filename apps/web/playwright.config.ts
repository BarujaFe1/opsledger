import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

const WEB_PORT = 3100;
const API_PORT = 8000;
const WEB_URL = `http://127.0.0.1:${WEB_PORT}`;
const API_URL = `http://127.0.0.1:${API_PORT}`;

function resolveApiPython(): string {
  if (process.env.OPSLEDGER_API_PYTHON) return process.env.OPSLEDGER_API_PYTHON;
  const win = path.join(__dirname, "..", "api", ".venv", "Scripts", "python.exe");
  const nix = path.join(__dirname, "..", "api", ".venv", "bin", "python");
  if (fs.existsSync(win)) return win;
  if (fs.existsSync(nix)) return nix;
  return process.platform === "win32" ? "python" : "python3";
}

const apiPython = resolveApiPython();

/**
 * Critical path: home → demo ingest → dashboard → issues → report.
 * Build must embed NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 (see CI / package scripts).
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 45_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: WEB_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(process.env.PLAYWRIGHT_CHANNEL
          ? { channel: process.env.PLAYWRIGHT_CHANNEL as "chrome" | "msedge" | "chromium" }
          : {}),
      },
    },
  ],
  webServer: [
    {
      command: `"${apiPython}" -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: path.join(__dirname, "..", "api"),
      url: `${API_URL}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `npx next start -H 127.0.0.1 -p ${WEB_PORT}`,
      cwd: __dirname,
      url: WEB_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
