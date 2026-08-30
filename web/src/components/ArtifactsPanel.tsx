import { useEffect, useState } from "react";
import { FileText, Image as ImageIcon, FileArchive, FileCode, Download, RefreshCw, X, FolderOpen, Eye, ExternalLink } from "lucide-react";
import { WorkspaceFile, downloadUrl, fetchWorkspaceFiles, previewUrl } from "../lib/api";

interface Props {
  sessionId: string;
  onClose: () => void;
}

function iconFor(name: string) {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) return ImageIcon;
  if (["zip"].includes(ext)) return FileArchive;
  if (["py", "js", "ts", "tsx", "jsx", "json", "html", "css"].includes(ext)) return FileCode;
  return FileText;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatAge(ts: number): string {
  const secs = Date.now() / 1000 - ts;
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

/**
 * Artifacts panel — every file Meiko generates during a session (documents,
 * scripts, images, zip exports) stays visible and downloadable here, not
 * just mentioned once in the chat transcript and then forgotten. Inspired
 * by Open Design's artifact tree (nexu-io/open-design), where every
 * generated file in a project remains a first-class, browsable object
 * rather than a link buried in a chat log.
 */
export default function ArtifactsPanel({ sessionId, onClose }: Props) {
  const [files, setFiles] = useState<WorkspaceFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [previewing, setPreviewing] = useState<WorkspaceFile | null>(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await fetchWorkspaceFiles(sessionId);
      setFiles(data);
    } catch {
      setFiles([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 8000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  return (
    <div className="artifacts-panel">
      <div className="artifacts-header">
        <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <FolderOpen size={15} /> Artifacts
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          <button className="icon-btn" title="Refresh" onClick={refresh}>
            <RefreshCw size={14} className={loading ? "spin-icon" : ""} />
          </button>
          <button className="icon-btn" title="Close" onClick={onClose}>
            <X size={15} />
          </button>
        </div>
      </div>
      <div className="artifacts-list">
        {files.length === 0 && !loading && (
          <div className="field-hint" style={{ padding: "16px 4px" }}>
            No files generated in this session yet — ask Meiko to write code, make a document, generate an
            image, or zip up a project, and it'll show up here instantly.
          </div>
        )}
        {files.map((f) => {
          const Icon = iconFor(f.name);
          return (
            <div key={f.name + f.kind} className="artifact-row" title={f.name} style={{ paddingRight: 4 }}>
              <Icon size={16} />
              <div className="artifact-meta">
                <span className="artifact-name">{f.name}</span>
                <span className="artifact-sub">
                  {formatSize(f.size_bytes)} · {formatAge(f.modified_at)} · {f.kind}
                </span>
              </div>
              {f.preview_url && (
                <button
                  className="icon-btn"
                  title="Live preview"
                  onClick={() => setPreviewing(f)}
                >
                  <Eye size={14} />
                </button>
              )}
              <a
                className="icon-btn"
                href={downloadUrl(sessionId, f.name.split("/").pop() || f.name)}
                target="_blank"
                rel="noreferrer"
                title={`Download ${f.name}`}
              >
                <Download size={13} className="artifact-download-icon" />
              </a>
            </div>
          );
        })}
      </div>
      {previewing && (
        <div className="preview-overlay" onClick={() => setPreviewing(null)}>
          <div className="preview-modal" onClick={(e) => e.stopPropagation()}>
            <div className="preview-modal-header">
              <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
                <Eye size={14} /> {previewing.name}
              </span>
              <div style={{ display: "flex", gap: 4 }}>
                <a
                  className="icon-btn"
                  href={previewUrl(sessionId, previewing.name)}
                  target="_blank"
                  rel="noreferrer"
                  title="Open in new tab"
                >
                  <ExternalLink size={14} />
                </a>
                <button className="icon-btn" title="Close" onClick={() => setPreviewing(null)}>
                  <X size={15} />
                </button>
              </div>
            </div>
            <iframe
              className="preview-modal-frame"
              src={previewUrl(sessionId, previewing.name)}
              title={previewing.name}
              sandbox="allow-scripts allow-forms allow-popups allow-modals"
            />
          </div>
        </div>
      )}
    </div>
  );
}
