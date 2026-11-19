import React, { useEffect, useRef } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FileText,
  Folder,
  FolderOpen,
} from "lucide-react";
import { FlatRow } from "../types";

interface TreeRowProps {
  row: FlatRow;
  isFocused: boolean;
  isCounterpartHovered: boolean;
  isCounterpartSelected: boolean;
  selectedKeys: Set<number>;
  onToggleExpand: (nodeId: string) => void;
  onToggleSelect: (itemKeys: number[]) => void;
  onHoverItem: (itemKey: number | null) => void;
  onClickItem: (itemKey: number) => void;
  onFocusRow: () => void;
}

export const TreeRow: React.FC<TreeRowProps> = ({
  row,
  isFocused,
  isCounterpartHovered,
  isCounterpartSelected,
  selectedKeys,
  onToggleExpand,
  onToggleSelect,
  onHoverItem,
  onClickItem,
  onFocusRow,
}) => {
  const { node, depth, isExpanded, hasChildren } = row;
  const checkboxRef = useRef<HTMLInputElement>(null);

  // Compute tri-state checkbox
  const totalSubtree = node.itemKeys.length;
  const selectedSubtree = node.itemKeys.filter((k) => selectedKeys.has(k)).length;
  const isChecked = totalSubtree > 0 && selectedSubtree === totalSubtree;
  const isIndeterminate = selectedSubtree > 0 && selectedSubtree < totalSubtree;

  useEffect(() => {
    if (checkboxRef.current) {
      checkboxRef.current.indeterminate = isIndeterminate;
    }
  }, [isIndeterminate]);

  const isFileSelected = !node.isFolder && node.itemKey !== undefined && selectedKeys.has(node.itemKey);
  const isDisabled = node.hasConflict;

  // Background styling for hover/counterpart/focus
  let bg = "transparent";
  if (isFocused) bg = "var(--bg-hover)";
  if (isFileSelected || isCounterpartSelected) bg = "var(--bg-selected)";
  if (isCounterpartHovered) bg = "var(--bg-counterpart)";

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isDisabled) return;
    onToggleSelect(node.itemKeys);
  };

  const handleRowClick = () => {
    onFocusRow();
    if (node.isFolder) {
      onToggleExpand(node.id);
    } else if (node.itemKey !== undefined) {
      onClickItem(node.itemKey);
    }
  };

  return (
    <div
      onClick={handleRowClick}
      onMouseEnter={() => {
        if (!node.isFolder && node.itemKey !== undefined) {
          onHoverItem(node.itemKey);
        }
      }}
      onMouseLeave={() => {
        onHoverItem(null);
      }}
      style={{
        display: "flex",
        alignItems: "center",
        height: "36px",
        paddingLeft: `${Math.max(8, depth * 20 + 8)}px`,
        paddingRight: "12px",
        backgroundColor: bg,
        borderBottom: "1px solid var(--border)",
        cursor: isDisabled ? "not-allowed" : "pointer",
        fontSize: "13px",
        transition: "background-color 0.1s ease",
        opacity: isDisabled ? 0.6 : 1,
      }}
    >
      {/* Expand/Collapse Chevron for Folders */}
      <div
        style={{ width: "20px", display: "flex", alignItems: "center", justifyContent: "center" }}
        onClick={(e) => {
          if (node.isFolder) {
            e.stopPropagation();
            onToggleExpand(node.id);
          }
        }}
      >
        {node.isFolder && hasChildren && (
          isExpanded ? (
            <ChevronDown size={14} color="var(--text-muted)" />
          ) : (
            <ChevronRight size={14} color="var(--text-muted)" />
          )
        )}
      </div>

      {/* Tri-state Checkbox */}
      <input
        type="checkbox"
        ref={checkboxRef}
        checked={isChecked}
        disabled={isDisabled}
        onChange={() => {}}
        onClick={handleCheckboxClick}
        style={{
          marginRight: "8px",
          cursor: isDisabled ? "not-allowed" : "pointer",
          accentColor: "var(--primary)",
        }}
      />

      {/* Node Icon */}
      <div style={{ marginRight: "8px", display: "flex", alignItems: "center" }}>
        {node.isFolder ? (
          isExpanded ? (
            <FolderOpen size={16} color="var(--primary)" />
          ) : (
            <Folder size={16} color="var(--primary)" />
          )
        ) : (
          <FileText size={15} color="var(--text-muted)" />
        )}
      </div>

      {/* Name */}
      <span
        style={{
          flex: 1,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          fontWeight: node.isFolder ? 600 : 400,
          color: node.isFolder ? "var(--text-main)" : "var(--text-main)",
        }}
        title={node.path}
      >
        {node.name}
      </span>

      {/* Metadata Badges for File Nodes */}
      {!node.isFolder && (
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginLeft: "12px" }}>
          {/* Category Badge */}
          {node.category && (
            <span
              style={{
                fontSize: "11px",
                padding: "2px 6px",
                borderRadius: "3px",
                backgroundColor: "var(--bg-app)",
                color: "var(--text-muted)",
                border: "1px solid var(--border)",
              }}
            >
              {node.category}
            </span>
          )}

          {/* Confidence Badge */}
          {node.confidence !== undefined && (
            <span
              style={{
                fontSize: "11px",
                fontFamily: "var(--font-mono)",
                padding: "2px 6px",
                borderRadius: "3px",
                fontWeight: 600,
                backgroundColor:
                  node.confidence >= 0.8
                    ? "var(--badge-approved-bg)"
                    : node.confidence >= 0.5
                    ? "var(--badge-pending-bg)"
                    : "var(--badge-failed-bg)",
                color:
                  node.confidence >= 0.8
                    ? "var(--badge-approved-text)"
                    : node.confidence >= 0.5
                    ? "var(--badge-pending-text)"
                    : "var(--badge-failed-text)",
              }}
            >
              {Math.round(node.confidence * 100)}%
            </span>
          )}

          {/* Rationale Tooltip Icon */}
          {node.rationale && (
            <span
              data-tooltip={node.rationale}
              style={{
                cursor: "help",
                fontSize: "11px",
                color: "var(--text-dim)",
                padding: "0 4px",
              }}
            >
              ℹ️
            </span>
          )}

          {/* Conflict Warning Indicator */}
          {node.hasConflict && (
            <span
              data-tooltip={node.conflictMessage || "Conflict detected"}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "3px",
                fontSize: "11px",
                color: "var(--warning)",
                fontWeight: 600,
                cursor: "help",
              }}
            >
              <AlertTriangle size={14} color="var(--warning)" />
              Conflict
            </span>
          )}
        </div>
      )}
    </div>
  );
};
