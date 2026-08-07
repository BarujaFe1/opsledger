import { cn, severityClass, severityLabel, statusClass, statusLabel } from "@/lib/utils";

export function Badge({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  return <Badge className={severityClass(severity)}>{severityLabel(severity)}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge className={statusClass(status)}>{statusLabel(status)}</Badge>;
}
