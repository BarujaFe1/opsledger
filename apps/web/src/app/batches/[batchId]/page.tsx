"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ChannelImpactChart, IssuesByTypeChart } from "@/components/Charts";
import { KpiCard, MoneyKpi } from "@/components/KpiCard";
import { exportIssuesUrl, getDashboard, getReport } from "@/lib/api";
import { parsePositiveInt, rememberBatchId } from "@/lib/routing";
import { severityLabel } from "@/lib/utils";
import type { Dashboard, Report } from "@/types";

export default function BatchDashboardPage() {
  const params = useParams();
  const batchId = parsePositiveInt(params.batchId);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showReport, setShowReport] = useState(false);

  useEffect(() => {
    if (batchId == null) {
      setLoading(false);
      setError("ID de batch inválido.");
      return;
    }
    rememberBatchId(batchId);
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getDashboard(batchId);
        if (!cancelled) setDash(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Erro ao carregar dashboard");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [batchId]);

  async function loadReport() {
    if (batchId == null) return;
    try {
      const r = await getReport(batchId);
      setReport(r);
      setShowReport(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao gerar relatório");
    }
  }

  function downloadReport() {
    if (!report) return;
    const blob = new Blob([report.content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `opsledger-batch-${report.batch_id}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-5 py-12" role="status" aria-live="polite">
        <div className="h-8 w-48 animate-pulse rounded bg-ink-200/70" />
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-2xl bg-ink-100" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !dash || batchId == null) {
    return (
      <div className="mx-auto max-w-6xl px-5 py-12">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-900" role="alert">
          {error || "Batch não encontrado"}
        </div>
        <Link href="/wizard?mode=demo" className="mt-4 inline-block text-sm text-accent underline">
          Rodar demo novamente
        </Link>
      </div>
    );
  }

  const critical = dash.issues_by_severity.find((s) => s.severity === "critical")?.count || 0;
  const openCount = dash.open_issues_count ?? dash.total_issues;

  return (
    <div className="mx-auto max-w-6xl px-5 py-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent">Dashboard · Batch #{batchId}</p>
          <h1 className="mt-2 font-display text-4xl text-ink-900">Fechamento operacional</h1>
          <p className="mt-2 text-ink-600">
            KPIs do batch · {openCount} issue{openCount === 1 ? "" : "s"} em aberto
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/batches/${batchId}/issues`}
            className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white"
          >
            Issues Register
          </Link>
          <a
            href={exportIssuesUrl(batchId)}
            className="rounded-full border border-ink-300 bg-white px-4 py-2 text-sm font-semibold text-ink-800"
          >
            Exportar CSV
          </a>
          <button
            type="button"
            onClick={loadReport}
            className="rounded-full border border-ink-300 bg-white px-4 py-2 text-sm font-semibold text-ink-800"
          >
            Relatório
          </button>
        </div>
      </div>

      {dash.total_issues === 0 ? (
        <div className="mt-8 rounded-2xl border border-accent/30 bg-accent-muted/50 p-5">
          <p className="font-semibold text-ink-900">Nenhum problema encontrado</p>
          <p className="mt-1 text-sm text-ink-600">O batch está limpo. Você pode gerar o relatório de fechamento.</p>
        </div>
      ) : null}

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <KpiCard label="Total de pedidos" value={dash.total_orders} />
        <MoneyKpi label="Valor total de pedidos" amount={dash.total_order_amount} />
        <MoneyKpi label="Valor conciliado (aberto)" amount={dash.reconciled_amount} tone="good" />
        <MoneyKpi label="Valor em divergência (aberto)" amount={dash.unreconciled_amount} tone="warn" />
        <KpiCard label="Quantidade de issues" value={dash.total_issues} tone={dash.total_issues ? "warn" : "good"} />
        <KpiCard label="Issues críticas" value={critical} tone={critical ? "danger" : "good"} />
      </div>
      <p className="mt-3 text-xs text-ink-500">
        Valores conciliado/divergência refletem issues financeiras ainda abertas ou em revisão (não o snapshot congelado do import).
      </p>

      {dash.next_best_action ? (
        <div className="mt-8 rounded-2xl border border-ink-200 bg-ink-900 p-5 text-ink-50 shadow-soft">
          <p className="text-xs uppercase tracking-[0.16em] text-accent-muted">Próxima melhor ação</p>
          <p className="mt-2 text-base leading-relaxed">{dash.next_best_action}</p>
        </div>
      ) : null}

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-ink-200 bg-white/80 p-5 shadow-soft">
          <h2 className="font-display text-2xl">Issues por tipo</h2>
          <div className="mt-4">
            <IssuesByTypeChart data={dash.issues_by_type} />
          </div>
        </div>
        <div className="rounded-2xl border border-ink-200 bg-white/80 p-5 shadow-soft">
          <h2 className="font-display text-2xl">Impacto por canal</h2>
          <div className="mt-4">
            <ChannelImpactChart data={dash.top_channels_with_divergence} />
          </div>
        </div>
      </div>

      <div className="mt-8 rounded-2xl border border-ink-200 bg-white/80 p-5">
        <h2 className="font-display text-2xl">Severidade</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          {dash.issues_by_severity.length === 0 ? (
            <p className="text-sm text-ink-500">Sem issues.</p>
          ) : (
            dash.issues_by_severity.map((s) => (
              <div key={s.severity} className="rounded-xl border border-ink-200 px-4 py-3">
                <p className="text-xs uppercase tracking-wider text-ink-500">{severityLabel(s.severity)}</p>
                <p className="font-display text-2xl">{s.count}</p>
              </div>
            ))
          )}
        </div>
      </div>

      {showReport && report ? (
        <div className="mt-8 rounded-2xl border border-ink-200 bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-display text-2xl">Relatório executivo</h2>
            <div className="flex gap-3">
              <button type="button" className="text-sm font-medium text-accent" onClick={downloadReport}>
                Baixar .md
              </button>
              <button type="button" className="text-sm text-ink-500" onClick={() => setShowReport(false)}>
                Fechar
              </button>
            </div>
          </div>
          <pre className="mt-4 whitespace-pre-wrap font-sans text-sm leading-relaxed text-ink-700">{report.content}</pre>
        </div>
      ) : null}
    </div>
  );
}
