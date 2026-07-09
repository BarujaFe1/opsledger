import type { Dashboard, ImportPreview, Issue, IssueDetail, Report } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    const detail = data?.detail;
    if (typeof detail === "string") return detail;
    if (detail?.message) return detail.message;
    return JSON.stringify(detail || data);
  } catch {
    return res.statusText || "Erro desconhecido";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return res.json() as Promise<T>;
}

export async function runDemo(): Promise<ImportPreview> {
  return request<ImportPreview>("/demo/run", { method: "POST" });
}

export async function uploadImport(files: {
  orders: File;
  payments: File;
  stock_movements: File;
}): Promise<ImportPreview> {
  const form = new FormData();
  form.append("orders", files.orders);
  form.append("payments", files.payments);
  form.append("stock_movements", files.stock_movements);
  return request<ImportPreview>("/imports", { method: "POST", body: form });
}

export async function getDashboard(batchId: number): Promise<Dashboard> {
  return request<Dashboard>(`/imports/${batchId}/dashboard`);
}

export async function getIssues(
  batchId: number,
  filters: { severity?: string; issue_type?: string; status?: string; channel?: string } = {},
): Promise<Issue[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v) params.set(k, v);
  });
  const qs = params.toString();
  return request<Issue[]>(`/imports/${batchId}/issues${qs ? `?${qs}` : ""}`);
}

export async function getIssue(issueId: number): Promise<IssueDetail> {
  return request<IssueDetail>(`/issues/${issueId}`);
}

export async function patchIssue(
  issueId: number,
  body: { status: string; note?: string },
): Promise<IssueDetail> {
  return request<IssueDetail>(`/issues/${issueId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function getReport(batchId: number): Promise<Report> {
  return request<Report>(`/imports/${batchId}/report?format=markdown`);
}

export function exportIssuesUrl(batchId: number): string {
  return `${API_BASE}/imports/${batchId}/export/issues.csv`;
}

export { API_BASE };
