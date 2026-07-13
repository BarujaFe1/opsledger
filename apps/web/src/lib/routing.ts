/** Shared ID / route helpers for client pages. */

export function parsePositiveInt(value: unknown): number | null {
  if (value == null) return null;
  const raw = Array.isArray(value) ? value[0] : value;
  const n = typeof raw === "number" ? raw : Number(String(raw));
  if (!Number.isFinite(n) || n <= 0 || !Number.isInteger(n)) return null;
  return n;
}

export function rememberBatchId(batchId: number): void {
  try {
    sessionStorage.setItem("opsledger_batch_id", String(batchId));
  } catch {
    // ignore (SSR / private mode)
  }
}

export function readRememberedBatchId(): number | null {
  try {
    return parsePositiveInt(sessionStorage.getItem("opsledger_batch_id"));
  } catch {
    return null;
  }
}
