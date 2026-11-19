import React from "react";
import { CheckCircle2, RotateCcw, XCircle } from "lucide-react";

interface ConfirmModalProps {
  isOpen: boolean;
  type: "approve" | "reject" | "rollback";
  count: number;
  summaryItems?: { label: string; count: number }[];
  onConfirm: () => void;
  onCancel: () => void;
  isProcessing: boolean;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  type,
  count,
  summaryItems,
  onConfirm,
  onCancel,
  isProcessing,
}) => {
  if (!isOpen) return null;

  const title =
    type === "approve"
      ? `Approve & Move ${count} File${count > 1 ? "s" : ""}?`
      : type === "reject"
      ? `Reject ${count} Proposal${count > 1 ? "s" : ""}?`
      : `Rollback ${count} Operation${count > 1 ? "s" : ""}?`;

  const description =
    type === "approve"
      ? `Every move will be safely journaled, verified via SHA-256 checksums, and moved to its organized destination. Feedback will be recorded for future ML suggestions.`
      : type === "reject"
      ? `The selected proposals will be marked as rejected. This feedback will be recorded to train the classifier to avoid similar classifications in the future.`
      : `The selected files will be reversed back to their original source paths and verified.`;

  const confirmBtnText =
    type === "approve"
      ? `Yes, Approve & Move (${count})`
      : type === "reject"
      ? `Yes, Reject Proposals (${count})`
      : `Yes, Restore Files (${count})`;

  const confirmBtnBg =
    type === "approve"
      ? "var(--success)"
      : type === "reject"
      ? "var(--danger)"
      : "var(--primary)";

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "460px",
          backgroundColor: "var(--bg-card)",
          borderRadius: "8px",
          border: "1px solid var(--border)",
          padding: "20px",
          boxShadow: "0 10px 25px -5px rgba(0,0,0,0.3)",
          color: "var(--text-main)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "12px" }}>
          {type === "approve" ? (
            <CheckCircle2 size={24} color="var(--success)" />
          ) : type === "reject" ? (
            <XCircle size={24} color="var(--danger)" />
          ) : (
            <RotateCcw size={24} color="var(--primary)" />
          )}
          <h3 style={{ fontSize: "16px", fontWeight: 700 }}>{title}</h3>
        </div>

        <p style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "16px", lineHeight: "1.4" }}>
          {description}
        </p>

        {summaryItems && summaryItems.length > 0 && (
          <div
            style={{
              backgroundColor: "var(--bg-app)",
              borderRadius: "6px",
              padding: "10px 14px",
              marginBottom: "16px",
              border: "1px solid var(--border)",
              maxHeight: "140px",
              overflowY: "auto",
            }}
          >
            <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-dim)", textTransform: "uppercase" }}>
              Category Breakdown
            </span>
            <div style={{ marginTop: "6px", display: "flex", flexDirection: "column", gap: "4px" }}>
              {summaryItems.map((item) => (
                <div
                  key={item.label}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontSize: "12px",
                  }}
                >
                  <span style={{ color: "var(--text-main)" }}>{item.label}</span>
                  <strong style={{ fontFamily: "var(--font-mono)" }}>{item.count}</strong>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
          <button
            onClick={onCancel}
            disabled={isProcessing}
            style={{
              padding: "8px 14px",
              fontSize: "13px",
              fontWeight: 500,
              backgroundColor: "transparent",
              color: "var(--text-main)",
              border: "1px solid var(--border)",
              borderRadius: "5px",
              cursor: isProcessing ? "not-allowed" : "pointer",
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isProcessing}
            style={{
              padding: "8px 16px",
              fontSize: "13px",
              fontWeight: 600,
              backgroundColor: confirmBtnBg,
              color: "#ffffff",
              border: "none",
              borderRadius: "5px",
              cursor: isProcessing ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
            }}
          >
            {isProcessing ? "Executing..." : confirmBtnText}
          </button>
        </div>
      </div>
    </div>
  );
};
