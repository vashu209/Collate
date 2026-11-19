import React from "react";
import { FolderGit2, Moon, Play, RefreshCw, RotateCcw, Search, Sun } from "lucide-react";
import { StatusSummary } from "../types";

interface HeaderProps {
  currentView: "review" | "rollback";
  onViewChange: (view: "review" | "rollback") => void;
  status: StatusSummary | null;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  onOpenScan: () => void;
  onOpenPropose: () => void;
  onRefresh: () => void;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  onViewChange,
  status,
  theme,
  onToggleTheme,
  onOpenScan,
  onOpenPropose,
  onRefresh,
  isLoading,
}) => {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 20px",
        backgroundColor: "var(--bg-card)",
        borderBottom: "1px solid var(--border)",
        height: "60px",
      }}
    >
      {/* Brand & Tabs */}
      <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <FolderGit2 size={24} color="var(--primary)" />
          <span style={{ fontWeight: 700, fontSize: "16px", letterSpacing: "-0.5px" }}>
            Autonomous File Organizer
          </span>
        </div>

        {/* View Switcher Tabs */}
        <div
          style={{
            display: "flex",
            backgroundColor: "var(--bg-app)",
            padding: "3px",
            borderRadius: "6px",
            border: "1px solid var(--border)",
          }}
        >
          <button
            onClick={() => onViewChange("review")}
            style={{
              padding: "5px 14px",
              fontSize: "13px",
              fontWeight: 600,
              borderRadius: "4px",
              border: "none",
              cursor: "pointer",
              backgroundColor: currentView === "review" ? "var(--bg-card)" : "transparent",
              color: currentView === "review" ? "var(--primary)" : "var(--text-muted)",
              boxShadow: currentView === "review" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            New Scan Review
          </button>
          <button
            onClick={() => onViewChange("rollback")}
            style={{
              padding: "5px 14px",
              fontSize: "13px",
              fontWeight: 600,
              borderRadius: "4px",
              border: "none",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              backgroundColor: currentView === "rollback" ? "var(--bg-card)" : "transparent",
              color: currentView === "rollback" ? "var(--primary)" : "var(--text-muted)",
              boxShadow: currentView === "rollback" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            <RotateCcw size={13} />
            Rollback Review
          </button>
        </div>
      </div>

      {/* Metrics & Actions */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        {status && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              fontSize: "12px",
              color: "var(--text-muted)",
            }}
          >
            <span>
              Scanned: <strong style={{ color: "var(--text-main)" }}>{status.total_files_scanned}</strong>
            </span>
            <span>•</span>
            <span>
              Pending:{" "}
              <strong style={{ color: "var(--warning)" }}>{status.proposals_pending}</strong>
            </span>
            <span>•</span>
            <span>
              Executed:{" "}
              <strong style={{ color: "var(--success)" }}>{status.operations_completed}</strong>
            </span>
            <span>•</span>
            <span>
              Feedback: <strong style={{ color: "var(--text-main)" }}>{status.feedback_records}</strong>
            </span>
          </div>
        )}

        {/* Task Trigger Buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            onClick={onOpenScan}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              fontSize: "12px",
              fontWeight: 500,
              backgroundColor: "var(--bg-app)",
              color: "var(--text-main)",
              border: "1px solid var(--border)",
              borderRadius: "5px",
              cursor: "pointer",
            }}
          >
            <Search size={14} />
            Scan...
          </button>
          <button
            onClick={onOpenPropose}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              fontSize: "12px",
              fontWeight: 500,
              backgroundColor: "var(--bg-app)",
              color: "var(--text-main)",
              border: "1px solid var(--border)",
              borderRadius: "5px",
              cursor: "pointer",
            }}
          >
            <Play size={14} />
            Propose...
          </button>
          <button
            onClick={onRefresh}
            title="Refresh Data"
            style={{
              padding: "6px",
              backgroundColor: "var(--bg-app)",
              color: "var(--text-main)",
              border: "1px solid var(--border)",
              borderRadius: "5px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <RefreshCw size={14} className={isLoading ? "spin" : ""} />
          </button>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={onToggleTheme}
          title={`Switch to ${theme === "dark" ? "Light" : "Dark"} Mode`}
          style={{
            padding: "6px",
            backgroundColor: "var(--bg-app)",
            color: "var(--text-main)",
            border: "1px solid var(--border)",
            borderRadius: "5px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {theme === "dark" ? <Sun size={15} color="#f59e0b" /> : <Moon size={15} />}
        </button>
      </div>
    </header>
  );
};
