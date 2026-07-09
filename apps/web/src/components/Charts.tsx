"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Dashboard } from "@/types";
import { formatBRL, issueTypeLabel } from "@/lib/utils";

export function IssuesByTypeChart({ data }: { data: Dashboard["issues_by_type"] }) {
  const chartData = data.map((d) => ({
    name: issueTypeLabel(d.issue_type),
    count: d.count,
  }));

  if (!chartData.length) {
    return <EmptyChart label="Nenhuma issue para plotar" />;
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#d0dbd5" />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#5a7367" }} angle={-25} textAnchor="end" interval={0} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#5a7367" }} />
          <Tooltip
            contentStyle={{ borderRadius: 12, borderColor: "#d0dbd5", fontSize: 13 }}
          />
          <Bar dataKey="count" fill="#1f6f5b" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ChannelImpactChart({
  data,
}: {
  data: Dashboard["top_channels_with_divergence"];
}) {
  const chartData = data.map((d) => ({
    name: d.channel,
    impact: Number(d.impact.toFixed(2)),
  }));

  if (!chartData.length) {
    return <EmptyChart label="Sem impacto por canal" />;
  }

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#d0dbd5" />
          <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#5a7367" }} />
          <YAxis tick={{ fontSize: 12, fill: "#5a7367" }} tickFormatter={(v) => `R$${v}`} />
          <Tooltip
            formatter={(value: number) => formatBRL(value)}
            contentStyle={{ borderRadius: 12, borderColor: "#d0dbd5", fontSize: 13 }}
          />
          <Bar dataKey="impact" fill="#c45c26" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-ink-200 bg-ink-50/60 text-sm text-ink-500">
      {label}
    </div>
  );
}
