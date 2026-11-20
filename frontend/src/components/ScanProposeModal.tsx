import React, { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, FolderOpen, Loader2, Play, Search, X } from "lucide-react";
import { api, browseFolder } from "../api/client";
import { TaskStatus } from "../types";

interface ScanProposeModalProps {
  mode: "scan" | "propose" | null;
  onClose: () => void;
  onSuccess: () => void;
  defaultScanRoot?: string;
}

export const ScanProposeModal: React.FC<ScanProposeModalProps> = ({
  mode,
  onClose,
  onSuccess,
  defaultScanRoot = "",
}) => {
  const [scanPath, setScanPath] = useState(defaultScanRoot);
  const [recursive, setRecursive] = useState(false);

  const [model, setModel] = useState("rules");
  const [minConfidence, setMinConfidence] = useState(0.5);

  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // NEW: State for folder browsing
  const [isBrowsing, setIsBrowsing] = useState(false);

  // Poll task progress if active
  useEffect(() => {
    if (!taskId) return;

    const interval = setInterval(async () => {
      try {
        const res = await api.getTaskStatus(taskId);
        setTaskStatus(res);
        if (res.status === "completed") {
          clearInterval(interval);
          onSuccess();
        } else if (res.status === "failed") {
          clearInterval(interval);
          setError(res.error || "Operation failed.");
        }
      } catch (err: any) {
        clearInterval(interval);
        setError(err.message || "Failed polling task.");
      }
    }, 400);

    return () => clearInterval(interval);
  }, [taskId, onSuccess]);

  if (!mode) return null;

  // NEW: Handle opening the native folder picker
  const handleBrowse = async () => {
    try {
      setIsBrowsing(true);
      const selectedPath = await browseFolder();
      if (selectedPath) {
        setScanPath(selectedPath);
      }
    } catch (err) {
      console.error("Failed to open folder picker", err);
    } finally {
      setIsBrowsing(false);
    }
  };

  const handleStartScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scanPath.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await api.startScan(scanPath.trim(), recursive);
      setTaskId(res.task_id);
    } catch (err: any) {
      setError(err.message);
      setIsSubmitting(false);
    }
  };

  const handleStartPropose = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await api.startPropose({
        model,
        min_confidence: minConfidence,
      });
      setTaskId(res.task_id);
    } catch (err: any) {
      setError(err.message);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "480px",
          backgroundColor: "var(--bg-card)",
          borderRadius: "8px",
          border: "1px solid var(--border)",
          padding: "20px",
          boxShadow: "0 10px 25px -5px rgba(0,0,0,0.3)",
          color: "var(--text-main)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {mode === "scan" ? <Search size={20} color="var(--primary)" /> : <Play size={20} color="var(--primary)" />}
            <h3 style={{ fontSize: "16px", fontWeight: 700 }}>
              {mode === "scan" ? "Scan Directory for Files" : "Generate Proposals"}
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{ border: "none", background: "transparent", cursor: "pointer", color: "var(--text-dim)" }}
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: "10px 12px",
              backgroundColor: "var(--badge-failed-bg)",
              color: "var(--badge-failed-text)",
              borderRadius: "6px",
              marginBottom: "16px",
              fontSize: "12px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {/* In-progress polling view */}
        {taskId && taskStatus ? (
          <div style={{ padding: "20px 0", textAlign: "center" }}>
            {taskStatus.status === "completed" ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
                <CheckCircle2 size={36} color="var(--success)" />
                <h4 style={{ fontSize: "15px", fontWeight: 600 }}>Task Completed!</h4>
                <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>{taskStatus.message}</p>
                <button
                  onClick={onClose}
                  style={{
                    marginTop: "12px",
                    padding: "6px 16px",
                    borderRadius: "4px",
                    backgroundColor: "var(--primary)",
                    color: "#fff",
                    border: "none",
                    cursor: "pointer",
                    fontSize: "13px",
                  }}
                >
                  Done
                </button>
              </div>
            ) : taskStatus.status === "failed" ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
                <AlertCircle size={36} color="var(--danger)" />
                <h4 style={{ fontSize: "15px", fontWeight: 600 }}>Task Failed</h4>
                <p style={{ fontSize: "13px", color: "var(--danger)" }}>{taskStatus.error}</p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
                <Loader2 size={32} className="spin" color="var(--primary)" />
                <h4 style={{ fontSize: "14px", fontWeight: 600 }}>Running background job...</h4>
                <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  {taskStatus.message || "Working..."}
                </p>
                {taskStatus.progress > 0 && (
                  <span style={{ fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--text-dim)" }}>
                    {taskStatus.progress} files processed
                  </span>
                )}
              </div>
            )}
          </div>
        ) : mode === "scan" ? (
          <form onSubmit={handleStartScan} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
                Target Folder Path:
              </label>
              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  placeholder="e.g. C:/Users/Documents or /path/to/scan"
                  value={scanPath}
                  onChange={(e) => setScanPath(e.target.value)}
                  required
                  style={{
                    flex: 1,
                    padding: "8px 10px",
                    borderRadius: "5px",
                    border: "1px solid var(--border)",
                    backgroundColor: "var(--bg-app)",
                    color: "var(--text-main)",
                    fontSize: "13px",
                  }}
                />
                <button
                  type="button"
                  onClick={handleBrowse}
                  disabled={isBrowsing}
                  style={{
                    padding: "8px 12px",
                    borderRadius: "5px",
                    border: "1px solid var(--border)",
                    backgroundColor: "var(--bg-app)",
                    color: "var(--text-main)",
                    cursor: isBrowsing ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    fontSize: "13px",
                  }}
                >
                  <FolderOpen size={16} />
                  {isBrowsing ? "Opening..." : "Browse"}
                </button>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <input
                type="checkbox"
                id="recursive"
                checked={recursive}
                onChange={(e) => setRecursive(e.target.checked)}
              />
              <label htmlFor="recursive" style={{ fontSize: "13px", cursor: "pointer" }}>
                Scan subdirectories recursively
              </label>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "10px" }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: "8px 14px",
                  borderRadius: "5px",
                  border: "1px solid var(--border)",
                  backgroundColor: "transparent",
                  color: "var(--text-main)",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !scanPath.trim()}
                style={{
                  padding: "8px 16px",
                  borderRadius: "5px",
                  border: "none",
                  backgroundColor: "var(--primary)",
                  color: "#fff",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {isSubmitting ? "Starting..." : "Start Scan"}
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleStartPropose} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
                Classification Backend:
              </label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 10px",
                  borderRadius: "5px",
                  border: "1px solid var(--border)",
                  backgroundColor: "var(--bg-app)",
                  color: "var(--text-main)",
                  fontSize: "13px",
                }}
              >
                <option value="rules">rules (Deterministic YAML rules - Tier 0)</option>
                <option value="ml">ml (MiniLM ONNX kNN Embeddings - Tier 1)</option>
              </select>
            </div>

            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, marginBottom: "6px" }}>
                Minimum Confidence Threshold: ({Math.round(minConfidence * 100)}%)
              </label>
              <input
                type="range"
                min={0.1}
                max={1.0}
                step={0.05}
                value={minConfidence}
                onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
                style={{ width: "100%", cursor: "pointer" }}
              />
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "10px" }}>
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: "8px 14px",
                  borderRadius: "5px",
                  border: "1px solid var(--border)",
                  backgroundColor: "transparent",
                  color: "var(--text-main)",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                style={{
                  padding: "8px 16px",
                  borderRadius: "5px",
                  border: "none",
                  backgroundColor: "var(--primary)",
                  color: "#fff",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {isSubmitting ? "Generating..." : "Generate Proposals"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};