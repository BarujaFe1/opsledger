"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { SeverityBadge, StatusBadge } from "@/components/Badge";
import { getIssue, patchIssue } from "@/lib/api";
import { parsePositiveInt, rememberBatchId } from "@/lib/routing";
import { formatBRL, issueTypeLabel, statusLabel, STATUS_OPTIONS } from "@/lib/utils";
import type { IssueDetail } from "@/types";

export default function IssueDetailPage() {
  const params = useParams();
  const issueId = parsePositiveInt(params.issueId);
  const [issue, setIssue] = useState<IssueDetail | null>(null);
  const [status, setStatus] = useState("open");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (issueId == null) {
      setLoading(false);
      setError("ID de issue inválido.");
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await getIssue(issueId);
        if (!cancelled) {
          setIssue(data);
          setStatus(data.status);
          setNote(data.resolution_note || "");
          rememberBatchId(data.batch_id);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Erro ao carregar issue");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [issueId]);

  async function save() {
    if (!issue) return;
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await patchIssue(issue.id, { status, note: note || undefined });
      setIssue(updated);
      setMessage("Status atualizado. O dashboard passa a refletir apenas issues financeiras ainda abertas.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-5 py-12 text-ink-500" role="status">
        Carregando detalhe…
      </div>
    );
  }
  if (error && !issue) {
    return (
      <div className="mx-auto max-w-3xl px-5 py-12">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700" role="alert">
          {error}
        </div>
        <Link href="/wizard?mode=demo" className="mt-4 inline-block text-sm text-accent underline">
          Rodar demo
        </Link>
      </div>
    );
  }
  if (!issue) return null;

  return (
    <div className="mx-auto max-w-3xl px-5 py-10">
      <Link href={`/batches/${issue.batch_id}/issues`} className="text-sm text-ink-600 hover:text-ink-900">
        ← Issues Register
      </Link>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={issue.severity} />
        <StatusBadge status={issue.status} />
        <span className="text-xs text-ink-500">{issueTypeLabel(issue.issue_type)}</span>
      </div>
      <h1 className="mt-3 font-display text-3xl text-ink-900">{issue.title}</h1>
      <p className="mt-4 text-ink-700 leading-relaxed">{issue.description}</p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Info label="Entidade" value={`${issue.entity_type} · ${issue.entity_id}`} />
        <Info label="Impacto financeiro" value={formatBRL(issue.amount_impact)} />
      </div>

      <div className="mt-6 rounded-2xl border border-accent/25 bg-accent-muted/40 p-4">
        <p className="text-xs uppercase tracking-[0.14em] text-accent">Ação recomendada</p>
        <p className="mt-2 text-ink-800">{issue.recommended_action}</p>
      </div>

      <div className="mt-8 rounded-2xl border border-ink-200 bg-white/90 p-5 space-y-4">
        <h2 className="font-display text-2xl">Atualizar status</h2>
        <label className="block text-sm">
          <span className="text-ink-600">Status</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="mt-1 w-full rounded-xl border border-ink-200 px-3 py-2"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="text-ink-600">Nota</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            className="mt-1 w-full rounded-xl border border-ink-200 px-3 py-2"
            placeholder="O que foi verificado?"
          />
        </label>
        <button
          type="button"
          disabled={saving}
          onClick={save}
          className="rounded-full bg-ink-900 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {saving ? "Salvando…" : "Salvar"}
        </button>
        {message ? <p className="text-sm text-accent">{message}</p> : null}
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
      </div>

      <div className="mt-8">
        <h2 className="font-display text-2xl">Timeline de status</h2>
        {issue.history?.length ? (
          <ol className="mt-4 space-y-3 border-l border-ink-200 pl-4">
            {issue.history.map((h) => (
              <li key={h.id} className="relative">
                <span className="absolute -left-[1.35rem] top-1.5 h-2.5 w-2.5 rounded-full bg-accent" />
                <p className="text-sm font-medium text-ink-800">
                  {statusLabel(h.previous_status)} → {statusLabel(h.new_status)}
                </p>
                <p className="text-xs text-ink-500">{new Date(h.changed_at).toLocaleString("pt-BR")}</p>
                {h.note ? <p className="mt-1 text-sm text-ink-600">{h.note}</p> : null}
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-3 text-sm text-ink-500">Sem histórico ainda.</p>
        )}
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-ink-200 bg-white/80 p-4">
      <p className="text-xs uppercase tracking-wider text-ink-500">{label}</p>
      <p className="mt-1 font-medium text-ink-900">{value}</p>
    </div>
  );
}
