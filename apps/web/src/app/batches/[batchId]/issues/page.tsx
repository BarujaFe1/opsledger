"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { SeverityBadge, StatusBadge } from "@/components/Badge";
import { getIssues } from "@/lib/api";
import { parsePositiveInt, rememberBatchId } from "@/lib/routing";
import { formatBRL, issueTypeLabel, SEVERITY_OPTIONS, STATUS_OPTIONS } from "@/lib/utils";
import type { Issue } from "@/types";

const ISSUE_TYPE_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "missing_payment", label: "Pagamento ausente" },
  { value: "orphan_payment", label: "Pagamento órfão" },
  { value: "amount_mismatch", label: "Divergência de valor" },
  { value: "duplicate_order", label: "Pedido duplicado" },
  { value: "missing_stock_out", label: "Baixa de estoque ausente" },
  { value: "negative_stock", label: "Estoque negativo" },
  { value: "channel_standardization", label: "Canal não padronizado" },
];

export default function IssuesPage() {
  const params = useParams();
  const batchId = parsePositiveInt(params.batchId);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severity, setSeverity] = useState("");
  const [issueType, setIssueType] = useState("");
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");

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
        const data = await getIssues(batchId, {
          severity: severity || undefined,
          issue_type: issueType || undefined,
          status: status || undefined,
          channel: channel || undefined,
        });
        if (!cancelled) setIssues(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Erro ao listar issues");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [batchId, severity, issueType, status, channel]);

  const columns = useMemo<ColumnDef<Issue>[]>(
    () => [
      {
        accessorKey: "severity",
        header: "Severidade",
        cell: ({ row }) => <SeverityBadge severity={row.original.severity} />,
      },
      {
        accessorKey: "issue_type",
        header: "Tipo",
        cell: ({ row }) => issueTypeLabel(row.original.issue_type),
      },
      {
        accessorKey: "title",
        header: "Título",
        cell: ({ row }) => (
          <Link href={`/issues/${row.original.id}`} className="font-medium text-ink-900 hover:text-accent">
            {row.original.title}
          </Link>
        ),
      },
      {
        accessorKey: "amount_impact",
        header: "Impacto",
        cell: ({ row }) => formatBRL(row.original.amount_impact),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
    ],
    [],
  );

  const table = useReactTable({
    data: issues,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  return (
    <div className="mx-auto max-w-6xl px-5 py-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent">Issues Register</p>
          <h1 className="mt-2 font-display text-4xl text-ink-900">
            Divergências {batchId != null ? `do batch #${batchId}` : ""}
          </h1>
        </div>
        {batchId != null ? (
          <Link href={`/batches/${batchId}`} className="text-sm text-ink-600 hover:text-ink-900">
            ← Dashboard
          </Link>
        ) : null}
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Select
          label="Severidade"
          value={severity}
          onChange={setSeverity}
          options={[{ value: "", label: "Todas" }, ...SEVERITY_OPTIONS]}
        />
        <Select label="Tipo" value={issueType} onChange={setIssueType} options={ISSUE_TYPE_OPTIONS} />
        <Select
          label="Status"
          value={status}
          onChange={setStatus}
          options={[{ value: "", label: "Todos" }, ...STATUS_OPTIONS]}
        />
        <label className="block text-sm">
          <span className="text-ink-600">Canal</span>
          <input
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            placeholder="ex: Shopify"
            className="mt-1 w-full rounded-xl border border-ink-200 bg-white px-3 py-2"
          />
        </label>
      </div>

      {loading ? (
        <p className="mt-8 text-ink-500 animate-pulse-soft" role="status">
          Carregando issues…
        </p>
      ) : error ? (
        <div className="mt-8 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-900" role="alert">
          {error}
          <div className="mt-3">
            <Link href="/wizard?mode=demo" className="text-sm underline">
              Rodar demo
            </Link>
          </div>
        </div>
      ) : issues.length === 0 ? (
        <div className="mt-8 rounded-2xl border border-dashed border-ink-300 bg-white/70 p-8 text-center">
          <p className="font-display text-2xl text-ink-900">Nenhum problema encontrado</p>
          <p className="mt-2 text-ink-600">Ajuste os filtros ou rode uma nova importação.</p>
        </div>
      ) : (
        <div className="mt-8 overflow-x-auto rounded-2xl border border-ink-200 bg-white/90 shadow-soft">
          <table className="min-w-full text-sm">
            <thead className="border-b border-ink-200 bg-ink-50/80 text-left text-xs uppercase tracking-wider text-ink-500">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => (
                    <th key={h.id} className="px-4 py-3 font-medium">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b border-ink-100 last:border-0 hover:bg-ink-50/60">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3 align-top">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: readonly { value: string; label: string }[] | { value: string; label: string }[];
}) {
  return (
    <label className="block text-sm">
      <span className="text-ink-600">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-xl border border-ink-200 bg-white px-3 py-2"
      >
        {options.map((opt) => (
          <option key={opt.value || "all"} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}
