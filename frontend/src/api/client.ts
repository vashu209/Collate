import {
  ExecutionResponse,
  OperationItem,
  ProposalItem,
  RollbackResponse,
  StatusSummary,
  TaskStatus,
} from "../types";

const BASE_URL = "";

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    let errorMsg = `HTTP Error ${res.status}: ${res.statusText}`;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorMsg = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore
    }
    throw new Error(errorMsg);
  }

  return res.json();
}

export const api = {
  getStatus: () => request<StatusSummary>("/status"),

  getProposals: (params?: { status?: string; category?: string; min_conf?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.append("status", params.status);
    if (params?.category) q.append("category", params.category);
    if (params?.min_conf !== undefined) q.append("min_conf", params.min_conf.toString());
    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return request<{ proposals: ProposalItem[]; total: number }>(`/proposals${queryStr}`);
  },

  approveProposals: (ids: number[]) =>
    request<ExecutionResponse>("/proposals/approve", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),

  rejectProposals: (ids: number[]) =>
    request<ExecutionResponse>("/proposals/reject", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),

  getOperations: () =>
    request<{ operations: OperationItem[]; total: number }>("/operations"),

  rollback: (body: {
    operation_id?: number;
    operation_ids?: number[];
    last_n?: number;
    all_completed?: boolean;
  }) =>
    request<RollbackResponse>("/rollback", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  startScan: (path: string, recursive: boolean = true) =>
    request<TaskStatus>("/scan", {
      method: "POST",
      body: JSON.stringify({ path, recursive }),
    }),

  startPropose: (body: {
    model?: string;
    min_confidence?: number;
    organize_root?: string;
    no_fallback?: boolean;
  }) =>
    request<TaskStatus>("/propose", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getTaskStatus: (taskId: string) => request<TaskStatus>(`/tasks/${taskId}`),
};

export async function browseFolder(): Promise<string | null> {
  const res = await fetch("/browse-folder", {
    method: "POST", // Forces the browser to not cache
  });
  if (!res.ok) throw new Error("Failed to open folder picker");
  const data = await res.json();
  return data.path;
}