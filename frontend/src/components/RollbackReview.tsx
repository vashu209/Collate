import React, { useMemo, useState } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { OperationItem } from "../types";
import { buildTreeFromItems, TreeSourceItem } from "../utils/tree";
import { ConfirmModal } from "./ConfirmModal";
import { VirtualDualTree } from "./VirtualDualTree";

interface RollbackReviewProps {
  operations: OperationItem[];
  onRollback: (operationIds: number[]) => Promise<void>;
  isLoading: boolean;
}

export const RollbackReview: React.FC<RollbackReviewProps> = ({
  operations,
  onRollback,
  isLoading,
}) => {
  const [selectedOpIds, setSelectedOpIds] = useState<Set<number>>(new Set());
  const [hoveredOpId, setHoveredOpId] = useState<number | null>(null);
  const [activeOpId, setActiveOpId] = useState<number | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  // Filter out already rolled_back operations if any
  const completedOps = useMemo(
    () => operations.filter((op) => op.status === "completed"),
    [operations]
  );

  // Build Left Tree ("Current" location = op.destination_path)
  const leftTreeNodes = useMemo(() => {
    const items: TreeSourceItem[] = completedOps.map((op) => ({
      key: op.id,
      path: op.destination_path,
      status: op.status,
      hasConflict: op.has_conflict,
      conflictType: op.conflict_type,
      conflictMessage: op.conflict_message,
    }));
    return buildTreeFromItems(items);
  }, [completedOps]);

  // Build Right Tree ("After Rollback" location = op.source_path)
  const rightTreeNodes = useMemo(() => {
    const items: TreeSourceItem[] = completedOps.map((op) => ({
      key: op.id,
      path: op.source_path,
      status: op.status,
      hasConflict: op.has_conflict,
      conflictType: op.conflict_type,
      conflictMessage: op.conflict_message,
    }));
    return buildTreeFromItems(items);
  }, [completedOps]);

  const handleToggleSelect = (itemKeys: number[]) => {
    setSelectedOpIds((prev) => {
      const next = new Set(prev);
      // Exclude conflicted operations
      const validKeys = itemKeys.filter((k) => {
        const op = completedOps.find((o) => o.id === k);
        return op && !op.has_conflict;
      });

      const allSelected = validKeys.every((k) => next.has(k));
      if (allSelected) {
        for (const k of validKeys) next.delete(k);
      } else {
        for (const k of validKeys) next.add(k);
      }
      return next;
    });
  };

  const handleSelectAllValid = () => {
    const validIds = completedOps.filter((o) => !o.has_conflict).map((o) => o.id);
    setSelectedOpIds(new Set(validIds));
  };

  const handleClearSelection = () => {
    setSelectedOpIds(new Set());
  };

  const handleExecuteRollback = async () => {
    setIsProcessing(true);
    try {
      await onRollback(Array.from(selectedOpIds));
      setSelectedOpIds(new Set());
      setIsConfirmOpen(false);
    } finally {
      setIsProcessing(false);
    }
  };

  const conflictedCount = completedOps.filter((o) => o.has_conflict).length;

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
      {/* Rollback Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 20px",
          backgroundColor: "var(--bg-card)",
          borderBottom: "1px solid var(--border)",
          gap: "12px",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "13px", fontWeight: 600 }}>
            Completed Moves Available for Rollback ({completedOps.length})
          </span>
          {conflictedCount > 0 && (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "12px",
                color: "var(--warning)",
                backgroundColor: "var(--badge-conflict-bg)",
                padding: "2px 8px",
                borderRadius: "4px",
                fontWeight: 500,
              }}
            >
              <AlertTriangle size={13} />
              {conflictedCount} conflict{conflictedCount > 1 ? "s" : ""} detected (disabled)
            </span>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={handleSelectAllValid}
            style={{
              padding: "4px 10px",
              fontSize: "12px",
              borderRadius: "4px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg-app)",
              color: "var(--text-main)",
              cursor: "pointer",
            }}
          >
            Select All Valid
          </button>
          {selectedOpIds.size > 0 && (
            <button
              onClick={handleClearSelection}
              style={{
                padding: "4px 8px",
                fontSize: "12px",
                borderRadius: "4px",
                border: "none",
                background: "transparent",
                color: "var(--text-dim)",
                cursor: "pointer",
              }}
            >
              Clear
            </button>
          )}
          <button
            disabled={selectedOpIds.size === 0 || isLoading}
            onClick={() => setIsConfirmOpen(true)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "5px 14px",
              fontSize: "12px",
              fontWeight: 600,
              borderRadius: "5px",
              border: "none",
              backgroundColor: selectedOpIds.size === 0 ? "var(--text-dim)" : "var(--primary)",
              color: "#fff",
              cursor: selectedOpIds.size === 0 ? "not-allowed" : "pointer",
              boxShadow: selectedOpIds.size > 0 ? "0 1px 3px rgba(0,0,0,0.2)" : "none",
            }}
          >
            <RotateCcw size={14} />
            Rollback Selected ({selectedOpIds.size})
          </button>
        </div>
      </div>

      {/* Synchronized Dual Tree */}
      <VirtualDualTree
        leftTitle="Current Location"
        leftSubtitle="Where organized files are now"
        leftNodes={leftTreeNodes}
        rightTitle="After Rollback (Original Location)"
        rightSubtitle="Restored destination on reversal"
        rightNodes={rightTreeNodes}
        selectedKeys={selectedOpIds}
        onToggleSelect={handleToggleSelect}
        hoveredKey={hoveredOpId}
        onHoverKey={setHoveredOpId}
        activeKey={activeOpId}
        onActiveKeyChange={setActiveOpId}
      />

      {/* Confirmation Modal */}
      <ConfirmModal
        isOpen={isConfirmOpen}
        type="rollback"
        count={selectedOpIds.size}
        onConfirm={handleExecuteRollback}
        onCancel={() => setIsConfirmOpen(false)}
        isProcessing={isProcessing}
      />
    </div>
  );
};
