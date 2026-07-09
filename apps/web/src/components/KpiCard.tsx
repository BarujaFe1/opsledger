import { cn, formatBRL } from "@/lib/utils";

export function KpiCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "default" | "good" | "warn" | "danger";
}) {
  const toneClass = {
    default: "border-ink-200",
    good: "border-accent/30",
    warn: "border-amber-300",
    danger: "border-red-300",
  }[tone];

  return (
    <div
      className={cn(
        "rounded-2xl border bg-white/80 p-5 shadow-soft backdrop-blur-sm animate-fade-up",
        toneClass,
      )}
    >
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ink-500">{label}</p>
      <p className="mt-2 font-display text-3xl font-semibold text-ink-900 tabular-nums">
        {typeof value === "number" && label.toLowerCase().includes("valor")
          ? formatBRL(value)
          : value}
      </p>
      {hint ? <p className="mt-2 text-sm text-ink-500">{hint}</p> : null}
    </div>
  );
}

export function MoneyKpi({
  label,
  amount,
  hint,
  tone = "default",
}: {
  label: string;
  amount: number;
  hint?: string;
  tone?: "default" | "good" | "warn" | "danger";
}) {
  return <KpiCard label={label} value={formatBRL(amount)} hint={hint} tone={tone} />;
}
