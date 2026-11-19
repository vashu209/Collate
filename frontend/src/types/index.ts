export type ItemStatus = "pending" | "approved" | "executed" | "rejected" | "failed";

export interface StatusSummary {
  total_files_scanned: number;
  proposals_pending: number;
  proposals_approved: number;
  proposals_rejected: number;
  proposals_executed: number;
  operations_completed: number;
  operations_rolled_back: number;
  operations_failed: number;
  feedback_records: number;
  latest_scan_root?: string;
}

export interface ProposalItem {
  id: number;
  file_id?: number;
  source_path: string;
  proposed_category: string;
  proposed_destination: string;
  confidence: number;
  rationale: string;
  status: ItemStatus;
  created_at: number;
}

export interface OperationItem {
  id: number;
  file_id?: number;
  proposal_id?: number;
  source_path: string;
  destination_path: string;
  checksum: string;
  status: string;
  timestamp: number;
  rolled_back_at?: number;
  has_conflict: boolean;
  conflict_type?: "missing_destination" | "file_modified" | "source_occupied" | "read_error";
  conflict_message?: string;
}

export interface ItemExecutionResult {
  id: number;
  success: boolean;
  status: string;
  destination?: string;
  error?: string;
}

export interface ExecutionResponse {
  results: ItemExecutionResult[];
  succeeded: number;
  failed: number;
}

export interface RollbackItemResult {
  operation_id: number;
  success: boolean;
  message: string;
  restored_path?: string;
}

export interface RollbackResponse {
  results: RollbackItemResult[];
  succeeded: number;
  failed: number;
}

export interface TaskStatus {
  task_id: string;
  task_type: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  message?: string;
  result?: Record<string, any>;
  error?: string;
}

// Tree data structures
export interface TreeNode {
  id: string;              // unique node key: e.g. "dir:D:/Docs" or "file:42"
  name: string;            // label for display
  path: string;            // full path of directory or file
  isFolder: boolean;
  itemKey?: number;        // proposal id or operation id
  category?: string;
  confidence?: number;
  rationale?: string;
  status?: ItemStatus | string;
  hasConflict?: boolean;
  conflictType?: string;
  conflictMessage?: string;
  children: TreeNode[];
  itemKeys: number[];      // all leaf itemKeys in subtree (for fast checkbox evaluation)
}

export interface FlatRow {
  node: TreeNode;
  depth: number;
  isExpanded: boolean;
  hasChildren: boolean;
}
