import { useEffect, useMemo, useState } from "react";
import { api } from "./api/client";
import { ConfirmModal } from "./components/ConfirmModal";
import { EmptyState } from "./components/EmptyState";
import { FilterBar } from "./components/FilterBar";
import { Header } from "./components/Header";
import { RollbackReview } from "./components/RollbackReview";
import { ScanProposeModal } from "./components/ScanProposeModal";
import { VirtualDualTree } from "./components/VirtualDualTree";
import { useTheme } from "./hooks/useTheme";
import { OperationItem, ProposalItem, StatusSummary } from "./types";
import { buildTreeFromItems, TreeSourceItem } from "./utils/tree";

export function App() {
  const { theme, toggleTheme } = useTheme();

  // App Navigation
  const [currentView, setCurrentView] = useState<"review" | "rollback">("review");

  // Core Data
  const [status, setStatus] = useState<StatusSummary | null>(null);
  const [proposals, setProposals] = useState<ProposalItem[]>([]);
  const [operations, setOperations] = useState<OperationItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Filters & Sorting for Review
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [minConfidence, setMinConfidence] = useState<number>(0);
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [sortByConfidence, setSortByConfidence] = useState<boolean>(true);

  // Selection & Interactivity
  const [selectedProposalIds, setSelectedProposalIds] = useState<Set<number>>(new Set());
  const [hoveredProposalId, setHoveredProposalId] = useState<number | null>(null);
  const [activeProposalId, setActiveProposalId] = useState<number | null>(null);

  // Modals & Action States
  const [modalMode, setModalMode] = useState<"scan" | "propose" | null>(null);
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    type: "approve" | "reject";
  }>({ isOpen: false, type: "approve" });
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [notification, setNotification] = useState<{
    type: "success" | "error" | "info";
    message: string;
  } | null>(null);

  // Initial Data Fetch
  const loadData = async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const [statusRes, proposalsRes, opsRes] = await Promise.all([
        api.getStatus(),
        api.getProposals({ status: "all" }),
        api.getOperations(),
      ]);
      setStatus(statusRes);
      setProposals(proposalsRes.proposals);
      setOperations(opsRes.operations);
    } catch (err: any) {
      setLoadError(err.message || "Failed to connect to backend server.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Distinct categories available in proposals
  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const p of proposals) {
      if (p.proposed_category) set.add(p.proposed_category);
    }
    return Array.from(set).sort();
  }, [proposals]);

  // Filtered proposals for review
  const filteredProposals = useMemo(() => {
    return proposals.filter((p) => {
      if (statusFilter !== "all" && p.status !== statusFilter) return false;
      if (selectedCategory && p.proposed_category.toLowerCase() !== selectedCategory.toLowerCase()) {
        return false;
      }
      if (minConfidence > 0 && p.confidence < minConfidence) return false;
      return true;
    });
  }, [proposals, statusFilter, selectedCategory, minConfidence]);

  // Sorted proposals
  const sortedProposals = useMemo(() => {
    const list = [...filteredProposals];
    if (sortByConfidence) {
      list.sort((a, b) => b.confidence - a.confidence);
    }
    return list;
  }, [filteredProposals, sortByConfidence]);

  // Left Tree Nodes ("Before": source_path)
  const leftTreeNodes = useMemo(() => {
    const items: TreeSourceItem[] = sortedProposals.map((p) => ({
      key: p.id,
      path: p.source_path,
      category: p.proposed_category,
      confidence: p.confidence,
      rationale: p.rationale,
      status: p.status,
    }));
    return buildTreeFromItems(items);
  }, [sortedProposals]);

  // Right Tree Nodes ("After": proposed_destination)
  const rightTreeNodes = useMemo(() => {
    const items: TreeSourceItem[] = sortedProposals.map((p) => ({
      key: p.id,
      path: p.proposed_destination,
      category: p.proposed_category,
      confidence: p.confidence,
      rationale: p.rationale,
      status: p.status,
    }));
    return buildTreeFromItems(items);
  }, [sortedProposals]);

  // Selection handlers
  const handleToggleSelect = (itemKeys: number[]) => {
    setSelectedProposalIds((prev) => {
      const next = new Set(prev);
      const allSelected = itemKeys.every((k) => next.has(k));
      if (allSelected) {
        for (const k of itemKeys) next.delete(k);
      } else {
        for (const k of itemKeys) next.add(k);
      }
      return next;
    });
  };

  const handleSelectAboveConfidence = (threshold: number) => {
    const ids = filteredProposals.filter((p) => p.confidence >= threshold).map((p) => p.id);
    setSelectedProposalIds(new Set(ids));
  };

  const handleSelectAllFiltered = () => {
    const ids = filteredProposals.map((p) => p.id);
    setSelectedProposalIds(new Set(ids));
  };

  const handleClearSelection = () => {
    setSelectedProposalIds(new Set());
  };

  // Execution Handlers (Approve / Reject)
  const handleConfirmAction = async () => {
    const ids = Array.from(selectedProposalIds);
    if (ids.length === 0) return;

    setIsExecuting(true);
    try {
      if (confirmModal.type === "approve") {
        const res = await api.approveProposals(ids);
        setNotification({
          type: res.failed > 0 ? "error" : "success",
          message: `Approved: ${res.succeeded} moved successfully, ${res.failed} failed.`,
        });
      } else {
        const res = await api.rejectProposals(ids);
        setNotification({
          type: "info",
          message: `Rejected: ${res.succeeded} proposals recorded as feedback.`,
        });
      }
      setSelectedProposalIds(new Set());
      setConfirmModal({ isOpen: false, type: "approve" });
      await loadData();
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed executing proposal action.",
      });
    } finally {
      setIsExecuting(false);
    }
  };

  // Rollback Execution
  const handleRollback = async (operationIds: number[]) => {
    try {
      const res = await api.rollback({ operation_ids: operationIds });
      setNotification({
        type: res.failed > 0 ? "error" : "success",
        message: `Rollback completed: ${res.succeeded} restored, ${res.failed} failed.`,
      });
      await loadData();
    } catch (err: any) {
      setNotification({
        type: "error",
        message: err.message || "Failed executing rollback.",
      });
    }
  };

  // Category breakdown for confirm modal
  const confirmSummary = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of filteredProposals) {
      if (selectedProposalIds.has(p.id)) {
        counts[p.proposed_category] = (counts[p.proposed_category] || 0) + 1;
      }
    }
    return Object.entries(counts).map(([label, count]) => ({ label, count }));
  }, [filteredProposals, selectedProposalIds]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      {/* Header */}
      <Header
        currentView={currentView}
        onViewChange={(v) => {
          setCurrentView(v);
          setNotification(null);
        }}
        status={status}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenScan={() => setModalMode("scan")}
        onOpenPropose={() => setModalMode("propose")}
        onRefresh={loadData}
        isLoading={isLoading}
      />

      {/* Notification Toast Banner */}
      {notification && (
        <div
          style={{
            padding: "8px 20px",
            backgroundColor:
              notification.type === "success"
                ? "var(--badge-approved-bg)"
                : notification.type === "error"
                ? "var(--badge-failed-bg)"
                : "var(--badge-pending-bg)",
            color:
              notification.type === "success"
                ? "var(--badge-approved-text)"
                : notification.type === "error"
                ? "var(--badge-failed-text)"
                : "var(--badge-pending-text)",
            fontSize: "12px",
            fontWeight: 600,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <span>{notification.message}</span>
          <button
            onClick={() => setNotification(null)}
            style={{
              border: "none",
              background: "transparent",
              color: "inherit",
              cursor: "pointer",
              fontWeight: 700,
              padding: "0 4px",
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Body */}
      {isLoading && proposals.length === 0 ? (
        <EmptyState
          type="loading"
          title="Loading catalog & proposals..."
          message="Connecting to local Autonomous File Organizer service."
        />
      ) : loadError ? (
        <EmptyState
          type="error"
          title="Could Not Connect to Organizer API"
          message={loadError}
          actionLabel="Retry Connection"
          onAction={loadData}
        />
      ) : currentView === "rollback" ? (
        <RollbackReview
          operations={operations}
          onRollback={handleRollback}
          isLoading={isExecuting}
        />
      ) : (
        /* New Scan Review View */
        <div style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
          <FilterBar
            categories={categories}
            selectedCategory={selectedCategory}
            onCategoryChange={setSelectedCategory}
            minConfidence={minConfidence}
            onMinConfidenceChange={setMinConfidence}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            sortByConfidence={sortByConfidence}
            onToggleSortByConfidence={() => setSortByConfidence((prev) => !prev)}
            selectedCount={selectedProposalIds.size}
            totalFilteredCount={filteredProposals.length}
            onApproveSelected={() => setConfirmModal({ isOpen: true, type: "approve" })}
            onRejectSelected={() => setConfirmModal({ isOpen: true, type: "reject" })}
            onSelectAboveConfidence={handleSelectAboveConfidence}
            onClearSelection={handleClearSelection}
            onSelectAllFiltered={handleSelectAllFiltered}
          />

          {filteredProposals.length === 0 ? (
            <EmptyState
              type="empty"
              title="No Proposals Found"
              message={
                proposals.length === 0
                  ? "There are no pending proposals in the database. Scan a folder and run propose to generate suggestions."
                  : "No proposals match the current category, confidence, or status filters."
              }
              actionLabel={proposals.length === 0 ? "Scan a Directory" : "Reset Filters"}
              onAction={() => {
                if (proposals.length === 0) setModalMode("scan");
                else {
                  setSelectedCategory("");
                  setMinConfidence(0);
                  setStatusFilter("all");
                }
              }}
            />
          ) : (
            <VirtualDualTree
              leftTitle="Current Folder Structure (Before)"
              leftSubtitle="Original file locations"
              leftNodes={leftTreeNodes}
              rightTitle="Projected Organized Tree (After)"
              rightSubtitle="Categorized destination paths"
              rightNodes={rightTreeNodes}
              selectedKeys={selectedProposalIds}
              onToggleSelect={handleToggleSelect}
              hoveredKey={hoveredProposalId}
              onHoverKey={setHoveredProposalId}
              activeKey={activeProposalId}
              onActiveKeyChange={setActiveProposalId}
            />
          )}
        </div>
      )}

      {/* Confirmation Dialog */}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        type={confirmModal.type}
        count={selectedProposalIds.size}
        summaryItems={confirmSummary}
        onConfirm={handleConfirmAction}
        onCancel={() => setConfirmModal({ isOpen: false, type: "approve" })}
        isProcessing={isExecuting}
      />

      {/* Scan & Propose Dialog */}
      <ScanProposeModal
        mode={modalMode}
        onClose={() => setModalMode(null)}
        onSuccess={loadData}
        defaultScanRoot={status?.latest_scan_root || ""}
      />
    </div>
  );
}
