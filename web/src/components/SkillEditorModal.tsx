import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { X, Sparkles, Loader2 } from "lucide-react";
import { createSkill, fetchSkillDetail, updateSkill } from "../lib/api";

interface Props {
  /** undefined = creating a brand-new skill; set = editing an existing one. */
  skillId?: string;
  onClose: () => void;
  onSaved: () => void;
}

const PLACEHOLDER_BODY = `# Steps

1. First, ...
2. Then, ...
3. Finally, ...

## Notes
- Anything Meiko should double-check or watch out for.
- Example code snippets or templates it should follow.`;

/**
 * "Add a skill" editor — lets a user write a new SKILL.md (name,
 * description, trigger keywords, and the markdown playbook body) without
 * touching the filesystem. Mirrors the on-disk frontmatter format used by
 * the built-in skills (backend/skills/<id>/SKILL.md) exactly, so anything
 * saved here is picked up by the agent's list_skills/use_skill tools
 * immediately — this is Meiko's answer to Claude's "Agent Skills", made
 * end-user-authorable instead of developer-only.
 */
export default function SkillEditorModal({ skillId, onClose, onSaved }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [triggers, setTriggers] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(!!skillId);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!skillId) return;
    fetchSkillDetail(skillId)
      .then((s) => {
        setName(s.name);
        setDescription(s.description);
        setTriggers(s.triggers.join(", "));
        setBody(s.body);
      })
      .catch(() => setError("Could not load this skill."))
      .finally(() => setLoading(false));
  }, [skillId]);

  const handleSave = async () => {
    setError("");
    if (!name.trim()) return setError("Give your skill a name.");
    if (!body.trim()) return setError("Write the steps Meiko should follow.");
    setSaving(true);
    const draft = {
      name: name.trim(),
      description: description.trim(),
      triggers: triggers
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      body: body.trim(),
    };
    try {
      if (skillId) {
        await updateSkill(skillId, { ...draft, skill_id: skillId });
      } else {
        await createSkill(draft);
      }
      onSaved();
    } catch (e: any) {
      setError(e?.message || "Failed to save skill.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <motion.div
      className="modal-overlay"
      onClick={onClose}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.16 }}
      style={{ zIndex: 60 }}
    >
      <motion.div
        className="modal-panel glass-strong"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 16, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 12, scale: 0.97 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        style={{ maxWidth: 640, width: "94vw", maxHeight: "88vh", display: "flex", flexDirection: "column" }}
      >
        <div className="modal-header">
          <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Sparkles size={18} /> {skillId ? "Edit skill" : "Add a skill"}
          </h2>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        {loading ? (
          <div style={{ padding: 24, display: "flex", justifyContent: "center" }}>
            <Loader2 className="spin-icon" size={20} />
          </div>
        ) : (
          <div style={{ padding: "4px 20px 20px", overflowY: "auto" }}>
            <label className="field-label">Name</label>
            <input
              placeholder="e.g. Weekly Status Report"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{ marginBottom: 12 }}
            />

            <label className="field-label">Description</label>
            <input
              placeholder="One line: what this skill is for"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={{ marginBottom: 12 }}
            />

            <label className="field-label">Trigger keywords (comma-separated)</label>
            <input
              placeholder="e.g. status report, weekly update"
              value={triggers}
              onChange={(e) => setTriggers(e.target.value)}
              style={{ marginBottom: 12 }}
            />
            <div className="field-hint" style={{ marginBottom: 12 }}>
              Meiko checks these against your message to decide when to load this skill automatically.
            </div>

            <label className="field-label">Instructions (Markdown)</label>
            <textarea
              placeholder={PLACEHOLDER_BODY}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={12}
              style={{
                width: "100%",
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                fontSize: 12.5,
                resize: "vertical",
                marginBottom: 8,
              }}
            />
            <div className="field-hint" style={{ marginBottom: 14 }}>
              Step-by-step guidance, code templates, or examples Meiko should follow whenever this skill loads.
            </div>

            {error && (
              <div className="field-hint" style={{ color: "var(--danger, #ff6b6b)", marginBottom: 10 }}>
                {error}
              </div>
            )}

            <motion.button
              className="new-chat-btn"
              style={{ justifyContent: "center", width: "100%" }}
              onClick={handleSave}
              disabled={saving}
              whileHover={{ scale: saving ? 1 : 1.01 }}
              whileTap={{ scale: saving ? 1 : 0.98 }}
            >
              {saving ? "Saving…" : skillId ? "Save changes" : "Create skill"}
            </motion.button>
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}
