import React from "react";
import { CheckCheck, SlidersHorizontal, XCircle } from "lucide-react";

interface FilterBarProps {
  categories: string[];
  selectedCategory: string;
  onCategoryChange: (cat: string) => void;
  minConfidence: number;
  onMinConfidenceChange: (val: number) => void;
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
  sortByConfidence: boolean;
  onToggleSortByConfidence: () => void;
  selectedCount: number;
  totalFilteredCount: number;
  onApproveSelected: () => void;
  onRejectSelected: () => void;
  onSelectAboveConfidence: (threshold: number) => void;
  onClearSelection: () => void;
  onSelectAllFiltered: () => void;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  categories,
  selectedCategory,
  onCategoryChange,
  minConfidence,
  onMinConfidenceChange,
  statusFilter,
  onStatusFilterChange,
  sortByConfidence,
  onToggleSortByConfidence,
  selectedCount,
  totalFilteredCount,
  onApproveSelected,
  onRejectSelected,
  onSelectAboveConfidence,
  onClearSelection,
  onSelectAllFiltered,
}) => {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "8px 20px",
        backgroundColor: "var(--bg-card)",
        borderBottom: "1px solid var(--border)",
        gap: "16px",
        flexWrap: "wrap",
      }}
    >
      {/* Left: Filter Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        {/* Category Filter */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <label style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 500 }}>
            Category:
          </label>
          <select
            value={selectedCategory}
            onChange={(e) => onCategoryChange(e.target.value)}
            style={{
              padding: "4px 8px",
              fontSize: "12px",
              borderRadius: "4px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg-app)",
              color: "var(--text-main)",
            }}
          >
            <option value="">All Categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Confidence Filter Slider */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <label style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 500 }}>
            Min Conf:
          </label>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={minConfidence}
            onChange={(e) => onMinConfidenceChange(parseFloat(e.target.value))}
            style={{ width: "80px", cursor: "pointer" }}
          />
          <span style={{ fontSize: "12px", fontFamily: "var(--font-mono)", width: "36px" }}>
            {minConfidence > 0 ? `${Math.round(minConfidence * 100)}%` : "0%"}
          </span>
        </div>

        {/* Status Filter */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <label style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 500 }}>
            Status:
          </label>
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value)}
            style={{
              padding: "4px 8px",
              fontSize: "12px",
              borderRadius: "4px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg-app)",
              color: "var(--text-main)",
            }}
          >
            <option value="pending">Pending</option>
            <option value="executed">Executed</option>
            <option value="rejected">Rejected</option>
            <option value="all">All Statuses</option>
          </select>
        </div>

        {/* Sort Button */}
        <button
          onClick={onToggleSortByConfidence}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "5px",
            padding: "4px 8px",
            fontSize: "12px",
            borderRadius: "4px",
            border: "1px solid var(--border)",
            backgroundColor: sortByConfidence ? "var(--bg-selected)" : "var(--bg-app)",
            color: sortByConfidence ? "var(--primary)" : "var(--text-main)",
            cursor: "pointer",
          }}
        >
          <SlidersHorizontal size={13} />
          Sort by Confidence
        </button>
      </div>

      {/* Right: Quick Selection & Action Buttons */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
        {/* Quick Select Presets */}
        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <button
            onClick={() => onSelectAboveConfidence(0.8)}
            style={{
              padding: "3px 8px",
              fontSize: "11px",
              borderRadius: "4px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg-app)",
              color: "var(--text-muted)",
              cursor: "pointer",
            }}
          >
            Select &gt;80%
          </button>
          <button
            onClick={() => onSelectAboveConfidence(0.5)}
            style={{
              padding: "3px 8px",
              fontSize: "11px",
              borderRadius: "4px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg-app)",
              color: "var(--text-muted)",
              cursor: "pointer",
            }}
          >
            Select &gt;50%
          </button>
          <button
            onClick={onSelectAllFiltered}
            style={{
              padding: "3px 8px",
              fontSize: "11px",
              borderRadius: "4px",
              border: "1px solid var(--border)",
              backgroundColor: "var(--bg-app)",
              color: "var(--text-muted)",
              cursor: "pointer",
            }}
          >
            Select All ({totalFilteredCount})
          </button>
          {selectedCount > 0 && (
            <button
              onClick={onClearSelection}
              style={{
                padding: "3px 8px",
                fontSize: "11px",
                borderRadius: "4px",
                border: "none",
                backgroundColor: "transparent",
                color: "var(--text-dim)",
                cursor: "pointer",
              }}
            >
              Clear
            </button>
          )}
        </div>

        {/* Action Buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <button
            disabled={selectedCount === 0}
            onClick={onRejectSelected}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "5px",
              padding: "5px 12px",
              fontSize: "12px",
              fontWeight: 600,
              borderRadius: "5px",
              border: "1px solid var(--danger)",
              backgroundColor: "transparent",
              color: selectedCount === 0 ? "var(--text-dim)" : "var(--danger)",
              cursor: selectedCount === 0 ? "not-allowed" : "pointer",
              opacity: selectedCount === 0 ? 0.5 : 1,
            }}
          >
            <XCircle size={14} />
            Reject ({selectedCount})
          </button>

          <button
            disabled={selectedCount === 0}
            onClick={onApproveSelected}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "5px",
              padding: "5px 14px",
              fontSize: "12px",
              fontWeight: 600,
              borderRadius: "5px",
              border: "none",
              backgroundColor: selectedCount === 0 ? "var(--text-dim)" : "var(--success)",
              color: "#ffffff",
              cursor: selectedCount === 0 ? "not-allowed" : "pointer",
              opacity: selectedCount === 0 ? 0.5 : 1,
              boxShadow: selectedCount > 0 ? "0 1px 3px rgba(0,0,0,0.2)" : "none",
            }}
          >
            <CheckCheck size={14} />
            Approve ({selectedCount})
          </button>
        </div>
      </div>
    </div>
  );
};
