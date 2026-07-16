<div align="center">
  <img src="./assets/icon.png" alt="OpsLedger Logo" width="120" height="120" />

  <h1>OpsLedger</h1>

  <p><strong>Reconciliação operacional para e-commerces pequenos: pedidos, pagamentos e estoque com regras testáveis.</strong></p>
  <p><strong>Operational reconciliation for small e-commerce: orders, payments and stock with testable rules.</strong></p>

  <p>
    <a href="#pt-br">PT-BR</a> ·
    <a href="#english">English</a> ·
    <a href="#live-demo">Live Demo</a> ·
    <a href="#stack">Stack</a> ·
    <a href="#architecture">Architecture</a> ·
    <a href="#quick-start">Quick Start</a> ·
    <a href="#author">Author</a>
  </p>

  <p>
    <img alt="Next.js" src="https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs" />
    <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" />
    <img alt="Pandas" src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" />
    <img alt="Status" src="https://img.shields.io/badge/Status-Lab%20demo-22C55E?style=for-the-badge" />
    <img alt="License" src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
  </p>

  <p>
    <a href="https://opsledger-app.vercel.app"><strong>Live Demo</strong></a> ·
    <a href="https://github.com/BarujaFe1/opsledger"><strong>Repo</strong></a> ·
    <a href="https://barujafe.vercel.app/"><strong>Portfolio</strong></a> ·
    <a href="https://www.linkedin.com/in/barujafe/"><strong>LinkedIn</strong></a>
  </p>
</div>

<p align="center">
  <img src="./assets/hero-cover.png" alt="OpsLedger product overview" width="100%" />
</p>

> **Lab / demo notice:** OpsLedger is a **portfolio lab**, not a production ERP/WMS. The public demo uses synthetic data and a reconciliation engine with honest single-user limits (no auth, no multi-tenant, SQLite).

---

## PT-BR

### Visão geral
O **OpsLedger** cruza pedidos, pagamentos e movimentações de estoque, detecta divergências com regras rastreáveis e orienta o fechamento operacional — do import ao relatório.

### Problema
Pequenos e-commerces fecham a semana com planilhas que quase batem: pagamentos órfãos, pedidos pagos sem captura, divergências de valor, duplicidades e baixas de estoque faltantes.

### Para quem
Analistas operacionais, founders de e-commerce pequeno/médio e profissionais de dados que precisam mostrar reconciliação aplicada (não só um dashboard).

### Funcionalidades
- Demo sintética one-click ou import de CSVs (pedidos / pagamentos / estoque)
- Engine de reconciliação com regras testáveis (qualidade, financeiro, estoque)
- Dashboard executivo (conciliado vs. em divergência, próxima ação)
- Issues register com detalhe, timeline de status e priorização por impacto
- Export CSV e relatório de fechamento
- Testes da engine (`pytest`) e UI (`vitest`)

### Escopo e limites (honestos)
- **Não é produção:** sem autenticação, sem multiempresa
- SQLite single-user; estoque é saldo do batch, não WMS
- Sem integrações reais de marketplace/gateway
- Demo pública depende do deploy Vercel configurado neste repositório

---

## English

### Overview
**OpsLedger** joins orders, payments and stock movements, flags mismatches with traceable rules, and guides operational closing — from import to report.

### Problem
Small e-commerce teams close the week on spreadsheets that almost reconcile: orphan payments, paid orders without capture, amount mismatches, duplicates and missing stock deductions.

### Who it is for
Ops analysts, small/mid e-commerce founders, and data professionals who need applied reconciliation — not another vanity dashboard.

### Features
- One-click synthetic demo or CSV import (orders / payments / stock)
- Reconciliation engine with testable rules (quality, finance, stock)
- Executive dashboard (reconciled vs. open issues, next best action)
- Issues register with detail, status timeline and impact prioritization
- CSV export and closing report
- Engine tests (`pytest`) and UI tests (`vitest`)

### Scope and honest limits
- **Not production:** no auth, no multi-tenant
- SQLite single-user; stock is batch balance, not a WMS
- No real marketplace/payment-gateway integrations
- Public demo depends on the Vercel deploy in this repository

---

## Live Demo

| Surface | URL |
|---|---|
| **Public lab** | [https://opsledger-app.vercel.app](https://opsledger-app.vercel.app) |
| **GitHub** | [https://github.com/BarujaFe1/opsledger](https://github.com/BarujaFe1/opsledger) |

**How to try:** open the demo → **Rodar demo** → inspect KPIs → open a high-severity issue → change status → export / closing report.

---

## Screenshots

<table>
  <tr>
    <td width="50%"><img src="./assets/screenshots/01-home.png" alt="Home" /><br /><sub><strong>Home</strong></sub></td>
    <td width="50%"><img src="./assets/screenshots/02-wizard-demo.png" alt="Wizard" /><br /><sub><strong>Wizard / demo</strong></sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="./assets/screenshots/03-dashboard.png" alt="Dashboard" /><br /><sub><strong>Dashboard</strong></sub></td>
    <td width="50%"><img src="./assets/screenshots/04-issues.png" alt="Issues" /><br /><sub><strong>Issues</strong></sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="./assets/screenshots/05-issue-detail.png" alt="Issue detail" /><br /><sub><strong>Issue detail</strong></sub></td>
    <td width="50%"><img src="./assets/screenshots/06-report.png" alt="Report" /><br /><sub><strong>Closing report</strong></sub></td>
  </tr>
</table>

---

## Stack

| Layer | Technology |
|---|---|
| Web | Next.js 15, React 19, TypeScript, Tailwind, Recharts, TanStack Table, Zod, Vitest |
| API | FastAPI, Pydantic, Pandas, SQLAlchemy, SQLite, pytest |
| Ops | Docker Compose, Vercel (`vercel.json` frontend + FastAPI services) |

---

## Architecture

```txt
apps/
  api/          FastAPI — import batch, reconciliation engine, issues, reports
    app/reconciliation/
    app/services/
  web/          Next.js — landing, wizard, dashboard, issues, report UI
data/           demo / processed artifacts
assets/         icon, hero, screenshots
```

High-level flow: CSV/demo → schema validation → ImportBatch → rule engine → issues + KPIs → status updates → CSV export / closing report.

---

## Quick Start

**Prerequisites:** Node.js 20+, Python 3.12+, Git.

### Windows one-shot
```bash
.\start.bat
```
API on `:8000`, web on `:3000`.

### Manual

```bash
# API
cd apps/api
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
python scripts/generate_demo_data.py
uvicorn app.main:app --reload --port 8000

# Web (other terminal)
cd apps/web
npm install
copy .env.example .env.local    # Windows
# cp .env.example .env.local    # Linux/macOS
npm run dev
```

### Docker (optional)
```bash
docker compose up --build
```

---

## Technical decisions

- **Rules as code + tests** so reconciliation is auditable, not a black-box spreadsheet formula
- **SQLite + SQLAlchemy** for a zero-friction local demo without cloud dependencies
- **Executive UX first** (KPIs, next action, issue severity) instead of raw tables only
- **Pandas in the API** for batch validation and joins that match real ops exports

---

## Roadmap

- Auth + workspaces
- PostgreSQL + Alembic
- Configurable per-tenant rules
- Fuzzy matching across channels
- Alerts for critical issues
- Batch-to-batch comparison

---

## Author

**Felipe Alirio Baruja** — data / product / full-stack portfolio.

- Portfolio: [https://barujafe.vercel.app/](https://barujafe.vercel.app/)
- GitHub: [https://github.com/BarujaFe1](https://github.com/BarujaFe1)
- LinkedIn: [https://www.linkedin.com/in/barujafe/](https://www.linkedin.com/in/barujafe/)

---

## License

MIT — see [`LICENSE`](./LICENSE).
