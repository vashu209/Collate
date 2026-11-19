import React, { useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { FolderMinus, FolderPlus } from "lucide-react";
import { TreeNode } from "../types";
import { flattenTree, getAllFolderIds } from "../utils/tree";
import { TreeRow } from "./TreeRow";

interface VirtualDualTreeProps {
  leftTitle: string;
  leftSubtitle: string;
  leftNodes: TreeNode[];
  rightTitle: string;
  rightSubtitle: string;
  rightNodes: TreeNode[];
  selectedKeys: Set<number>;
  onToggleSelect: (itemKeys: number[]) => void;
  hoveredKey: number | null;
  onHoverKey: (key: number | null) => void;
  activeKey: number | null;
  onActiveKeyChange: (key: number | null) => void;
}

export const VirtualDualTree: React.FC<VirtualDualTreeProps> = ({
  leftTitle,
  leftSubtitle,
  leftNodes,
  rightTitle,
  rightSubtitle,
  rightNodes,
  selectedKeys,
  onToggleSelect,
  hoveredKey,
  onHoverKey,
  activeKey,
  onActiveKeyChange,
}) => {
   // Folder expansion state for left and right trees
  const [leftExpanded, setLeftExpanded] = useState<Set<string>>(new Set());
  const [rightExpanded, setRightExpanded] = useState<Set<string>>(new Set());

  // Track folder IDs we've already seeded, per side. Once a folder is in
  // this ref, its expansion state belongs to the user — never re-seed it.
  const seenFolderIdsRef = useRef<{ left: Set<string>; right: Set<string> }>({
    left: new Set(),
    right: new Set(),
  });

  // Seed expansion ONCE per folder ID. On later data refreshes, only
  // genuinely-new folders get auto-expanded; everything the user has
  // expanded or collapsed is preserved.
  useEffect(() => {
    const collectNew = (nodes: TreeNode[], side: "left" | "right"): Set<string> | null => {
      const seen = seenFolderIdsRef.current[side];
      const all = getAllFolderIds(nodes);
      const fresh = new Set<string>();
      for (const id of all) {
        if (!seen.has(id)) {
          fresh.add(id);
          seen.add(id);
        }
      }
      return fresh.size > 0 ? fresh : null;
    };

    const newLeft = collectNew(leftNodes, "left");
    const newRight = collectNew(rightNodes, "right");

    if (newLeft) {
      setLeftExpanded(prev => {
        const next = new Set(prev);
        for (const id of newLeft) next.add(id);
        return next;
      });
    }
    if (newRight) {
      setRightExpanded(prev => {
        const next = new Set(prev);
        for (const id of newRight) next.add(id);
        return next;
      });
    }
  }, [leftNodes, rightNodes]);
  
  // Flattened visible rows
  const leftRows = useMemo(
    () => flattenTree(leftNodes, leftExpanded),
    [leftNodes, leftExpanded]
  );
  const rightRows = useMemo(
    () => flattenTree(rightNodes, rightExpanded),
    [rightNodes, rightExpanded]
  );

  // Active focused row indices for keyboard navigation
  const [focusedSide, setFocusedSide] = useState<"left" | "right">("left");
  const [focusedIndex, setFocusedIndex] = useState<number>(0);

  const leftParentRef = useRef<HTMLDivElement>(null);
  const rightParentRef = useRef<HTMLDivElement>(null);

  const leftVirtualizer = useVirtualizer({
    count: leftRows.length,
    getScrollElement: () => leftParentRef.current,
    estimateSize: () => 36,
    overscan: 15,
  });

  const rightVirtualizer = useVirtualizer({
    count: rightRows.length,
    getScrollElement: () => rightParentRef.current,
    estimateSize: () => 36,
    overscan: 15,
  });

  // Keyboard navigation handler (Arrows to move, Space to toggle, Enter to expand)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is inside an input/select
      if (
        document.activeElement?.tagName === "INPUT" ||
        document.activeElement?.tagName === "SELECT" ||
        document.activeElement?.tagName === "TEXTAREA"
      ) {
        return;
      }

      const activeRows = focusedSide === "left" ? leftRows : rightRows;
      const virtualizer = focusedSide === "left" ? leftVirtualizer : rightVirtualizer;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setFocusedIndex((prev) => {
          const next = Math.min(prev + 1, activeRows.length - 1);
          virtualizer.scrollToIndex(next);
          return next;
        });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setFocusedIndex((prev) => {
          const next = Math.max(prev - 1, 0);
          virtualizer.scrollToIndex(next);
          return next;
        });
      } else if (e.key === "ArrowRight") {
        // Switch to right pane or expand folder
        const curr = activeRows[focusedIndex];
        if (curr && curr.node.isFolder && !curr.isExpanded) {
          e.preventDefault();
          toggleExpand(curr.node.id, focusedSide);
        } else if (focusedSide === "left") {
          e.preventDefault();
          setFocusedSide("right");
        }
      } else if (e.key === "ArrowLeft") {
        // Switch to left pane or collapse folder
        const curr = activeRows[focusedIndex];
        if (curr && curr.node.isFolder && curr.isExpanded) {
          e.preventDefault();
          toggleExpand(curr.node.id, focusedSide);
        } else if (focusedSide === "right") {
          e.preventDefault();
          setFocusedSide("left");
        }
      } else if (e.key === " ") {
        // Space toggles checkbox of current focused row
        e.preventDefault();
        const curr = activeRows[focusedIndex];
        if (curr && !curr.node.hasConflict) {
          onToggleSelect(curr.node.itemKeys);
        }
      } else if (e.key === "Enter") {
        const curr = activeRows[focusedIndex];
        if (curr && curr.node.isFolder) {
          e.preventDefault();
          toggleExpand(curr.node.id, focusedSide);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [focusedSide, focusedIndex, leftRows, rightRows, leftVirtualizer, rightVirtualizer, onToggleSelect]);

  const toggleExpand = (id: string, side: "left" | "right") => {
    const setFn = side === "left" ? setLeftExpanded : setRightExpanded;
    setFn((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAll = (side: "left" | "right") => {
    const all = getAllFolderIds(side === "left" ? leftNodes : rightNodes);
    if (side === "left") setLeftExpanded(all);
    else setRightExpanded(all);
  };

  const collapseAll = (side: "left" | "right") => {
    if (side === "left") setLeftExpanded(new Set());
    else setRightExpanded(new Set());
  };

  return (
    <div
      style={{
        display: "flex",
        flex: 1,
        height: "calc(100vh - 110px)",
        overflow: "hidden",
        backgroundColor: "var(--bg-app)",
      }}
    >
      {/* LEFT PANE */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid var(--border)",
          backgroundColor: "var(--bg-card)",
          minWidth: 0,
        }}
      >
        {/* Pane Header */}
        <div
          style={{
            padding: "8px 14px",
            backgroundColor: "var(--bg-card-header)",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <span style={{ fontWeight: 700, fontSize: "13px" }}>{leftTitle}</span>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", marginLeft: "8px" }}>
              {leftSubtitle} ({leftRows.length} visible rows)
            </span>
          </div>
          <div style={{ display: "flex", gap: "6px" }}>
            <button
              onClick={() => expandAll("left")}
              title="Expand All Folders"
              style={{
                border: "none",
                background: "transparent",
                cursor: "pointer",
                padding: "2px",
                color: "var(--text-muted)",
              }}
            >
              <FolderPlus size={15} />
            </button>
            <button
              onClick={() => collapseAll("left")}
              title="Collapse All Folders"
              style={{
                border: "none",
                background: "transparent",
                cursor: "pointer",
                padding: "2px",
                color: "var(--text-muted)",
              }}
            >
              <FolderMinus size={15} />
            </button>
          </div>
        </div>

        {/* Virtualized Left List */}
        <div
          ref={leftParentRef}
          style={{
            flex: 1,
            overflowY: "auto",
            position: "relative",
          }}
          onClick={() => setFocusedSide("left")}
        >
          {leftRows.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--text-dim)", fontSize: "13px" }}>
              No items to display.
            </div>
          ) : (
            <div
              style={{
                height: `${leftVirtualizer.getTotalSize()}px`,
                width: "100%",
                position: "relative",
              }}
            >
              {leftVirtualizer.getVirtualItems().map((virtualRow) => {
                const row = leftRows[virtualRow.index];
                const isFocused = focusedSide === "left" && focusedIndex === virtualRow.index;
                const isCounterpartHovered =
                  hoveredKey !== null &&
                  !row.node.isFolder &&
                  row.node.itemKey === hoveredKey;
                const isCounterpartSelected =
                  activeKey !== null &&
                  !row.node.isFolder &&
                  row.node.itemKey === activeKey;

                return (
                  <div
                    key={row.node.id}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: `${virtualRow.size}px`,
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    <TreeRow
                      row={row}
                      isFocused={isFocused}
                      isCounterpartHovered={isCounterpartHovered}
                      isCounterpartSelected={isCounterpartSelected}
                      selectedKeys={selectedKeys}
                      onToggleExpand={(id) => toggleExpand(id, "left")}
                      onToggleSelect={onToggleSelect}
                      onHoverItem={onHoverKey}
                      onClickItem={(key) => onActiveKeyChange(key)}
                      onFocusRow={() => {
                        setFocusedSide("left");
                        setFocusedIndex(virtualRow.index);
                      }}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* RIGHT PANE */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          backgroundColor: "var(--bg-card)",
          minWidth: 0,
        }}
      >
        {/* Pane Header */}
        <div
          style={{
            padding: "8px 14px",
            backgroundColor: "var(--bg-card-header)",
            borderBottom: "1px solid var(--border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <span style={{ fontWeight: 700, fontSize: "13px" }}>{rightTitle}</span>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", marginLeft: "8px" }}>
              {rightSubtitle} ({rightRows.length} visible rows)
            </span>
          </div>
          <div style={{ display: "flex", gap: "6px" }}>
            <button
              onClick={() => expandAll("right")}
              title="Expand All Folders"
              style={{
                border: "none",
                background: "transparent",
                cursor: "pointer",
                padding: "2px",
                color: "var(--text-muted)",
              }}
            >
              <FolderPlus size={15} />
            </button>
            <button
              onClick={() => collapseAll("right")}
              title="Collapse All Folders"
              style={{
                border: "none",
                background: "transparent",
                cursor: "pointer",
                padding: "2px",
                color: "var(--text-muted)",
              }}
            >
              <FolderMinus size={15} />
            </button>
          </div>
        </div>

        {/* Virtualized Right List */}
        <div
          ref={rightParentRef}
          style={{
            flex: 1,
            overflowY: "auto",
            position: "relative",
          }}
          onClick={() => setFocusedSide("right")}
        >
          {rightRows.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--text-dim)", fontSize: "13px" }}>
              No projected items to display.
            </div>
          ) : (
            <div
              style={{
                height: `${rightVirtualizer.getTotalSize()}px`,
                width: "100%",
                position: "relative",
              }}
            >
              {rightVirtualizer.getVirtualItems().map((virtualRow) => {
                const row = rightRows[virtualRow.index];
                const isFocused = focusedSide === "right" && focusedIndex === virtualRow.index;
                const isCounterpartHovered =
                  hoveredKey !== null &&
                  !row.node.isFolder &&
                  row.node.itemKey === hoveredKey;
                const isCounterpartSelected =
                  activeKey !== null &&
                  !row.node.isFolder &&
                  row.node.itemKey === activeKey;

                return (
                  <div
                    key={row.node.id}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: `${virtualRow.size}px`,
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    <TreeRow
                      row={row}
                      isFocused={isFocused}
                      isCounterpartHovered={isCounterpartHovered}
                      isCounterpartSelected={isCounterpartSelected}
                      selectedKeys={selectedKeys}
                      onToggleExpand={(id) => toggleExpand(id, "right")}
                      onToggleSelect={onToggleSelect}
                      onHoverItem={onHoverKey}
                      onClickItem={(key) => onActiveKeyChange(key)}
                      onFocusRow={() => {
                        setFocusedSide("right");
                        setFocusedIndex(virtualRow.index);
                      }}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
