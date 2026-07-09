"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { runDemo, uploadImport } from "@/lib/api";
import type { ImportPreview } from "@/types";

type Mode = "choose" | "demo" | "upload" | "preview";

export default function WizardClient() {
  const router = useRouter();
  const params = useSearchParams();
  const initial = params.get("mode");

  const [mode, setMode] = useState<Mode>("choose");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [ordersFile, setOrdersFile] = useState<File | null>(null);
  const [paymentsFile, setPaymentsFile] = useState<File | null>(null);
  const [stockFile, setStockFile] = useState<File | null>(null);

  useEffect(() => {
    if (initial === "demo") setMode("demo");
    if (initial === "upload") setMode("upload");
  }, [initial]);

  useEffect(() => {
    if (mode !== "demo") return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await runDemo();
        if (!cancelled) {
          setPreview(result);
          setMode("preview");
          sessionStorage.setItem("opsledger_batch_id", String(result.batch.id));
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Falha ao rodar demo");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode]);

  const canUpload = useMemo(
    () => Boolean(ordersFile && paymentsFile && stockFile),
    [ordersFile, paymentsFile, stockFile],
  );

  async function handleUpload() {
    if (!ordersFile || !paymentsFile || !stockFile) return;
    setLoading(true);
    setError(null);
    try {
      const result = await uploadImport({
        orders: ordersFile,
        payments: paymentsFile,
        stock_movements: stockFile,
      });
      setPreview(result);
      setMode("preview");
      sessionStorage.setItem("opsledger_batch_id", String(result.batch.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha no upload");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-5 py-12">
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent">Wizard</p>
      <h1 className="mt-2 font-display text-4xl text-ink-900">Carregar dados</h1>
      <p className="mt-3 text-ink-600 max-w-2xl">
        Use a demo sintética (150 pedidos, divergências intencionais) ou importe seus CSVs de pedidos, pagamentos e estoque.
      </p>

      {mode === "choose" && (
        <div className="mt-10 grid sm:grid-cols-2 gap-4">
          <button
            type="button"
            onClick={() => setMode("demo")}
            className="rounded-2xl border border-ink-200 bg-white/80 p-6 text-left shadow-soft hover:border-accent transition"
          >
            <p className="font-display text-2xl">Rodar demo</p>
            <p className="mt-2 text-sm text-ink-600">Carrega dados sintéticos realistas sem dependências externas.</p>
          </button>
          <button
            type="button"
            onClick={() => setMode("upload")}
            className="rounded-2xl border border-ink-200 bg-white/80 p-6 text-left shadow-soft hover:border-accent transition"
          >
            <p className="font-display text-2xl">Importar CSVs</p>
            <p className="mt-2 text-sm text-ink-600">Valida schema mínimo e executa a engine de reconciliação.</p>
          </button>
        </div>
      )}

      {mode === "demo" && loading && (
        <StateBox tone="loading" title="Processando demo…" body="Validando arquivos, cruzando regras e montando o batch." />
      )}

      {mode === "upload" && (
        <div className="mt-8 space-y-5 rounded-2xl border border-ink-200 bg-white/80 p-6 shadow-soft">
          <FileField label="Pedidos (orders.csv)" onChange={setOrdersFile} file={ordersFile} />
          <FileField label="Pagamentos (payments.csv)" onChange={setPaymentsFile} file={paymentsFile} />
          <FileField label="Estoque (stock_movements.csv)" onChange={setStockFile} file={stockFile} />
          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="button"
              disabled={!canUpload || loading}
              onClick={handleUpload}
              className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loading ? "Processando…" : "Validar e reconciliar"}
            </button>
            <button type="button" onClick={() => setMode("choose")} className="text-sm text-ink-600 underline-offset-2 hover:underline">
              Voltar
            </button>
          </div>
        </div>
      )}

      {error && <StateBox tone="error" title="Não foi possível processar" body={error} />}

      {mode === "preview" && preview && (
        <div className="mt-8 space-y-6">
          <StateBox
            tone="success"
            title={preview.batch.source_name === "demo" ? "Demo carregada com sucesso" : "Importação concluída"}
            body={`Batch #${preview.batch.id} · ${preview.batch.total_issues} issues · status ${preview.batch.status}`}
          />
          <div className="grid md:grid-cols-3 gap-4">
            <PreviewCard title="Pedidos" preview={preview.orders} />
            <PreviewCard title="Pagamentos" preview={preview.payments} />
            <PreviewCard title="Estoque" preview={preview.stock_movements} />
          </div>
          <button
            type="button"
            onClick={() => router.push(`/batches/${preview.batch.id}`)}
            className="rounded-full bg-ink-900 px-6 py-3 text-sm font-semibold text-white"
          >
            Ir para o dashboard
          </button>
        </div>
      )}
    </div>
  );
}

function FileField({
  label,
  file,
  onChange,
}: {
  label: string;
  file: File | null;
  onChange: (f: File | null) => void;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink-700">{label}</span>
      <input
        type="file"
        accept=".csv,text/csv"
        className="mt-2 block w-full text-sm text-ink-600 file:mr-4 file:rounded-full file:border-0 file:bg-accent-muted file:px-4 file:py-2 file:text-sm file:font-semibold file:text-accent"
        onChange={(e) => onChange(e.target.files?.[0] || null)}
      />
      {file ? <p className="mt-1 font-mono text-xs text-ink-500">{file.name}</p> : null}
    </label>
  );
}

function PreviewCard({
  title,
  preview,
}: {
  title: string;
  preview: ImportPreview["orders"];
}) {
  return (
    <div className="rounded-2xl border border-ink-200 bg-white/80 p-4">
      <p className="font-display text-xl">{title}</p>
      <p className="mt-1 text-sm text-ink-500">{preview.rows} linhas</p>
      <p className="mt-3 font-mono text-[11px] text-ink-400 break-all">{preview.columns.join(", ")}</p>
    </div>
  );
}

function StateBox({
  tone,
  title,
  body,
}: {
  tone: "loading" | "error" | "success";
  title: string;
  body: string;
}) {
  const styles = {
    loading: "border-ink-200 bg-white/80",
    error: "border-red-200 bg-red-50 text-red-900",
    success: "border-accent/30 bg-accent-muted/60 text-ink-900",
  }[tone];
  return (
    <div className={`mt-8 rounded-2xl border p-5 ${styles}`}>
      <p className="font-semibold">{title}</p>
      <p className={`mt-1 text-sm ${tone === "loading" ? "text-ink-600 animate-pulse-soft" : ""}`}>{body}</p>
    </div>
  );
}
