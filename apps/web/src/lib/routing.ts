/** Shared ID / route helpers for client pages. */

/**
 * Stateless public-demo sentinel. Mirrors `DEMO_BATCH_ID` on the API
 * (apps/api/app/services/import_service.py). The demo never writes to the DB;
 * batch -1 is a real, handled batch id in public-demo mode, so the frontend
 * MUST accept it as valid — not reject it as a "negative id".
 */
export const DEMO_BATCH_ID = -1;

/**
 * Parse a batch id from a route param / sessionStorage value.
 * Valid: positive integers (real batches) and the demo sentinel DEMO_BATCH_ID (-1).
 * Invalid: 0, numbers < -1, non-integers (e.g. 1.5), and non-numeric strings.
 */
export function parseBatchId(raw: string): number | null {
  const id = Number(raw);
  if (!Number.isInteger(id)) return null;
  if (id === DEMO_BATCH_ID || id > 0) return id;
  return null;
}

/**
 * Parse a positive integer (used for issue ids, which are always >= 1).
 * Negative / zero / non-integer values are rejected.
 */
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
    const stored = sessionStorage.getItem("opsledger_batch_id");
    return stored == null ? null : parseBatchId(stored);
  } catch {
    return null;
  }
}
