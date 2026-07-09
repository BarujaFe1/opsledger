import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBRL(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value || 0);
}

export function severityClass(severity: string): string {
  switch (severity) {
    case "critical":
      return "bg-red-100 text-red-800 border-red-200";
    case "high":
      return "bg-orange-100 text-orange-800 border-orange-200";
    case "medium":
      return "bg-amber-100 text-amber-900 border-amber-200";
    case "low":
      return "bg-sky-100 text-sky-800 border-sky-200";
    default:
      return "bg-ink-100 text-ink-700 border-ink-200";
  }
}

export function statusClass(status: string): string {
  switch (status) {
    case "open":
      return "bg-accent-muted text-accent border-accent/20";
    case "reviewing":
      return "bg-amber-50 text-amber-800 border-amber-200";
    case "resolved":
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    case "ignored":
      return "bg-ink-100 text-ink-600 border-ink-200";
    default:
      return "bg-ink-100 text-ink-700 border-ink-200";
  }
}

export function issueTypeLabel(type: string): string {
  const map: Record<string, string> = {
    missing_payment: "Pagamento ausente",
    orphan_payment: "Pagamento órfão",
    amount_mismatch: "Divergência de valor",
    duplicate_order: "Pedido duplicado",
    missing_stock_out: "Baixa de estoque ausente",
    negative_stock: "Estoque negativo",
    channel_standardization: "Canal não padronizado",
  };
  return map[type] || type;
}
