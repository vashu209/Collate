import React from "react";
import { AlertCircle, FolderSearch, Inbox, Loader2 } from "lucide-react";

interface EmptyStateProps {
  type: "loading" | "empty" | "error";
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  type,
  title,
  message,
  actionLabel,
  onAction,
}) => {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        flex: 1,
        padding: "60px 20px",
        textAlign: "center",
        color: "var(--text-muted)",
      }}
    >
      <div style={{ marginBottom: "16px" }}>
        {type === "loading" && <Loader2 size={40} className="spin" color="var(--primary)" />}
        {type === "empty" && <Inbox size={40} color="var(--text-dim)" />}
        {type === "error" && <AlertCircle size={40} color="var(--danger)" />}
      </div>

      <h3 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-main)", marginBottom: "6px" }}>
        {title}
      </h3>
      <p style={{ fontSize: "13px", maxWidth: "420px", lineHeight: "1.5", marginBottom: "20px" }}>
        {message}
      </p>

      {actionLabel && onAction && (
        <button
          onClick={onAction}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 16px",
            borderRadius: "5px",
            backgroundColor: "var(--primary)",
            color: "#fff",
            border: "none",
            fontSize: "13px",
            fontWeight: 600,
            cursor: "pointer",
            boxShadow: "0 1px 3px rgba(0,0,0,0.15)",
          }}
        >
          <FolderSearch size={15} />
          {actionLabel}
        </button>
      )}
    </div>
  );
};
