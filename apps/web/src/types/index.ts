export type ImportBatch = {
  id: number;
  created_at: string;
  source_name: string;
  status: string;
  total_orders: number;
  total_payments: number;
  total_stock_movements: number;
  total_issues: number;
  total_amount: number;
  reconciled_amount: number;
  unreconciled_amount: number;
};

export type PreviewRow = {
  rows: number;
  columns: string[];
  sample: Record<string, unknown>[];
};

export type ImportPreview = {
  batch: ImportBatch;
  orders: PreviewRow;
  payments: PreviewRow;
  stock_movements: PreviewRow;
};

export type Issue = {
  id: number;
  batch_id: number;
  issue_type: string;
  severity: "low" | "medium" | "high" | "critical" | string;
  entity_type: string;
  entity_id: string;
  title: string;
  description: string;
  recommended_action: string;
  amount_impact: number;
  status: "open" | "reviewing" | "resolved" | "ignored" | string;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  resolution_note?: string | null;
};

export type IssueHistory = {
  id: number;
  issue_id: number;
  previous_status: string;
  new_status: string;
  changed_at: string;
  note?: string | null;
};

export type IssueDetail = Issue & {
  history: IssueHistory[];
};

export type Dashboard = {
  batch_id: number;
  total_orders: number;
  total_order_amount: number;
  reconciled_amount: number;
  unreconciled_amount: number;
  total_issues: number;
  open_issues_count?: number;
  issues_by_severity: { severity: string; count: number }[];
  issues_by_type: { issue_type: string; count: number }[];
  top_channels_with_divergence: { channel: string; impact: number; issues: number }[];
  next_best_action?: string | null;
};

export type Report = {
  batch_id: number;
  format: string;
  content: string;
  generated_at: string;
};
