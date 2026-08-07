# Screenshot capture roteiro — OpsLedger

Capture after a local or public demo run. Prefer synthetic demo data (no real PII).

## Prep

1. `.\start.bat` or API + `npm run dev`
2. Hard refresh; window ≥ 1280×800
3. Theme: light (default)

## Shots

| File | URL / action | Focus |
|------|----------------|-------|
| `01-home.png` | `/` | Brand OpsLedger + CTAs (hero mock labeled illustrative) |
| `02-wizard-demo.png` | Rodar demo → preview | Batch `demo:monthly_closing_2026_06` success |
| `03-dashboard.png` | Ir para o dashboard | KPIs + next best action |
| `04-issues.png` | Issues Register | Table with severity/type filters |
| `05-issue-detail.png` | Open one issue | Rule, amount, status timeline |
| `06-report.png` | Relatório | Executive markdown panel |

## Naming

Store under `assets/screenshots/`. Keep filenames stable for README links.

## Demo 3–5 min (script)

1. **0:00** Dor: três CSVs no fechamento mensal (Marina).
2. **0:40** Rodar demo → batch `monthly_closing_2026_06`.
3. **1:30** Dashboard: divergência Decimal-backed + próxima ação.
4. **2:30** Issues → detalhe → marcar reviewing com nota.
5. **3:30** Relatório .md + mencionar pytest/Playwright/CI.
6. **4:30** Limitações: sem auth, SQLite `/tmp` no Vercel, lab MVP.
