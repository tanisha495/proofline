"use client";

import { useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CircleAlert,
  ClipboardCheck,
  FileCheck2,
  FileText,
  History,
  Link2,
  LockKeyhole,
  MessageSquare,
  Paperclip,
  PenLine,
  Play,
  Send,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import {
  blockers,
  channels,
  emptyIntent,
  emptyVisual,
  formatDate,
  sourceLabel,
} from "../lib/workflow.mjs";
import { extractDocument } from "../lib/documents";
import {
  Badge,
  Button,
  Empty,
  Field,
  Header,
  Modal,
  Risk,
  Status,
  Tabs,
} from "./ui";

function Editor({ draft, onSave, onCancel }) {
  const [fields, setFields] = useState(() => ({
    title: draft?.title ?? "",
    text: draft?.text ?? "",
    channel: draft?.channel ?? channels[0],
    intent: draft?.intent ?? emptyIntent,
    visual: draft?.visual ?? emptyVisual,
    attachment: draft?.attachment ?? "",
  }));
  const [mode, setMode] = useState("Paste text");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef(null);
  const update = (key, value) =>
    setFields((previous) => ({ ...previous, [key]: value }));
  async function load(file) {
    if (!file) return;
    setError("");
    setLoading(true);
    try {
      const text = await extractDocument(file);
      if (!text)
        throw new Error(
          "No selectable text was found. For a scanned document, paste its text into the editor."
        );
      setFields((previous) => ({
        ...previous,
        text,
        attachment: file.name,
        title: previous.title || file.name.replace(/\.[^.]+$/, ""),
      }));
      setMode("Paste text");
    } catch (problem) {
      setError(
        problem instanceof Error
          ? problem.message
          : "Could not read this document."
      );
    } finally {
      setLoading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }
  function save(run) {
    if (!fields.title.trim() || !fields.text.trim()) {
      setError("Add a title and some draft text before continuing.");
      return;
    }
    const colors = Object.values(fields.visual).map((value) => value.trim());
    if (
      colors.some(Boolean) &&
      !colors.every((value) => /^#[\da-f]{6}$/i.test(value))
    ) {
      setError(
        "Enter both colors as six-digit hex codes, such as #142139 and #FFFFFF."
      );
      return;
    }
    onSave(
      {
        ...fields,
        title: fields.title.trim(),
        text: fields.text.trim(),
        visual: { foreground: colors[0], background: colors[1] },
      },
      run
    );
  }
  return (
    <>
      <button className="back-link" type="button" onClick={onCancel}>
        <ArrowLeft size={16} /> {draft ? "Back to draft" : "Back to my drafts"}
      </button>
      <Header
        eyebrow="DRAFT WORKSPACE"
        title={draft ? "Edit draft" : "New draft"}
        description="Add your copy and tell ProofLine what the draft needs to preserve."
      />
      <form
        className="editor-grid"
        onSubmit={(event) => {
          event.preventDefault();
          save(true);
        }}
      >
        <section className="card section-card editor-card">
          <Tabs
            items={["Paste text", "Upload PDF / DOCX"]}
            value={mode}
            onChange={setMode}
            label="Draft input method"
          />
          <div className="editor-fields">
            <div className="field-row">
              <Field label="Draft name">
                <input
                  required
                  placeholder="e.g. Summer launch email"
                  value={fields.title}
                  onChange={(event) => update("title", event.target.value)}
                />
              </Field>
              <Field label="Channel">
                <select
                  value={fields.channel}
                  onChange={(event) => update("channel", event.target.value)}
                >
                  {channels.map((channel) => (
                    <option key={channel}>{channel}</option>
                  ))}
                </select>
              </Field>
            </div>
            {mode === "Upload PDF / DOCX" ? (
              <div className="upload-panel">
                <UploadCloud size={30} />
                <strong>
                  {loading ? "Extracting text…" : "Import a document"}
                </strong>
                <p>
                  PDF or DOCX up to 15 MB. Imported text is editable before
                  review.
                </p>
                <input
                  ref={fileInput}
                  type="file"
                  className="sr-only"
                  tabIndex={-1}
                  aria-label="Upload a PDF or DOCX"
                  accept=".pdf,.docx"
                  onChange={(event) => load(event.target.files?.[0])}
                />
                <Button
                  icon={Paperclip}
                  variant="secondary"
                  disabled={loading}
                  onClick={() => fileInput.current.click()}
                >
                  Choose file
                </Button>
              </div>
            ) : (
              <Field label="Draft text">
                <textarea
                  rows={12}
                  placeholder="Paste or write your draft here…"
                  value={fields.text}
                  onChange={(event) => update("text", event.target.value)}
                />
              </Field>
            )}
            {fields.attachment && (
              <p className="attachment">
                <Paperclip size={15} /> {fields.attachment}
              </p>
            )}
            <details
              className="intent-details"
              open={
                fields.visual.foreground || fields.visual.background
                  ? true
                  : undefined
              }
            >
              <summary>Check text contrast</summary>
              <div className="field-row contrast-fields">
                {[
                  ["foreground", "Text color", "#142139"],
                  ["background", "Background color", "#FFFFFF"],
                ].map(([key, label, placeholder]) => (
                  <Field key={key} label={label}>
                    <input
                      value={fields.visual[key]}
                      placeholder={placeholder}
                      onChange={(event) =>
                        update("visual", {
                          ...fields.visual,
                          [key]: event.target.value,
                        })
                      }
                    />
                  </Field>
                ))}
              </div>
            </details>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
          </div>
        </section>
        <section className="card section-card intent-card">
          <div className="section-heading">
            <div>
              <div className="heading-icon">
                <LockKeyhole size={19} />
                <h2>Intent Lock</h2>
              </div>
              <p>Capture what should stay the same when you revise the copy.</p>
            </div>
            <Badge>Optional</Badge>
          </div>
          <div className="intent-fields">
            {[
              ["message", "Message", "What should readers take away?"],
              ["audience", "Audience", "Who are you writing for?"],
              ["action", "Call to action", "What should readers do next?"],
            ].map(([key, label, placeholder]) => (
              <Field key={key} label={label}>
                <input
                  placeholder={placeholder}
                  value={fields.intent[key]}
                  onChange={(event) =>
                    update("intent", {
                      ...fields.intent,
                      [key]: event.target.value,
                    })
                  }
                />
              </Field>
            ))}
            <Button type="submit" icon={Play} disabled={loading}>
              Run checks
            </Button>
            <Button
              variant="secondary"
              disabled={loading}
              onClick={() => save(false)}
            >
              Save draft
            </Button>
          </div>
        </section>
      </form>
    </>
  );
}

const ledgerTones = {
  Supported: "green",
  Conflicts: "red",
  "Expired evidence": "amber",
  Unsupported: "red",
  "Needs a human": "amber",
};
function Claims({ claims, onSource }) {
  if (!claims.length)
    return (
      <Empty
        title="No claims in this check"
        detail="The demo ledger checks Starter plan pricing and common promotional claims."
        icon={FileCheck2}
      />
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Claim</th>
            <th>Status</th>
            <th>Evidence version</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim, index) => (
            <tr key={index}>
              <td>
                <strong>{claim.text}</strong>
              </td>
              <td>
                <Badge tone={ledgerTones[claim.status]}>{claim.status}</Badge>
              </td>
              <td>
                <button
                  className="text-button"
                  type="button"
                  onClick={() => onSource(claim.source)}
                >
                  {sourceLabel(claim.source)}
                </button>
                {claim.policy && (
                  <small className="table-subtle">Policy reference</small>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function DraftText({ draft, finding, onQuote }) {
  const ref = useRef(null);
  const text = draft.text;
  const start = finding?.start;
  const end = start + (finding?.original.length || 0);
  return (
    <section className="card section-card">
      <div className="section-heading">
        <div>
          <h2>Draft copy</h2>
          <p>
            {draft.channel} · Version {draft.version}
          </p>
        </div>
        <Badge>
          {draft.text.trim().split(/\s+/).filter(Boolean).length} words
        </Badge>
      </div>
      <div
        ref={ref}
        className="draft-copy"
        onMouseUp={() => {
          const selection = window.getSelection();
          if (
            onQuote &&
            selection?.anchorNode &&
            ref.current.contains(selection.anchorNode) &&
            ref.current.contains(selection.focusNode)
          ) {
            onQuote(selection.toString().trim().slice(0, 240));
          }
        }}
      >
        {finding && text.slice(start, end) === finding.original ? (
          <>
            {text.slice(0, start)}
            <mark>{text.slice(start, end)}</mark>
            {text.slice(end)}
          </>
        ) : (
          text
        )}
      </div>
    </section>
  );
}
function FindingPanel({
  draft,
  selected,
  onSelect,
  onSource,
  onAction,
  editable,
}) {
  return (
    <section className="card section-card">
      <div className="section-heading">
        <div>
          <h2>Findings</h2>
          <p>Each finding links to an approved source.</p>
        </div>
        <Badge tone={draft.findings.length ? "amber" : "green"}>
          {draft.findings.length}
        </Badge>
      </div>
      {!draft.checked ? (
        <Empty
          title="Checks are needed"
          detail="Run checks against the current brand library."
          icon={CircleAlert}
        />
      ) : !selected ? (
        <Empty
          title="No findings"
          detail="The configured demo checks found no issues in this version."
          icon={FileCheck2}
        />
      ) : (
        <div className="finding-body">
          {draft.findings.length > 1 && (
            <select
              aria-label="Choose finding"
              value={selected.id}
              onChange={(event) => onSelect(event.target.value)}
            >
              {draft.findings.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.severity} · {item.title} · {item.original}
                </option>
              ))}
            </select>
          )}
          <div className="finding-heading">
            <h3>{selected.title}</h3>
            <Badge tone={selected.severity === "Blocker" ? "red" : "amber"}>
              {selected.severity}
            </Badge>
          </div>
          <p>{selected.reason}</p>
          <div className="source-line">
            <Link2 size={16} />
            <button
              type="button"
              className="text-button"
              onClick={() => onSource(selected.source)}
            >
              {sourceLabel(selected.source)}
            </button>
            <Badge>{selected.confidence} confidence</Badge>
          </div>
          {selected.suggested && (
            <div className="comparison">
              <div>
                <small>ORIGINAL</small>
                <strong>{selected.original}</strong>
              </div>
              <ArrowRight size={17} />
              <div>
                <small>SUGGESTED</small>
                <strong>{selected.suggested}</strong>
              </div>
            </div>
          )}
          {draft.intentRecorded && (
            <details className="intent-details">
              <summary>
                <LockKeyhole size={15} /> Check against Intent Lock
              </summary>
              <dl>
                {Object.entries(draft.intent)
                  .filter(([, value]) => value)
                  .map(([key, value]) => (
                    <div key={key}>
                      <dt>{key === "action" ? "Call to action" : key}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
              </dl>
            </details>
          )}
          {selected.decision === "dismissed" && (
            <p className="callout compact">
              <strong>Dismissed</strong> {selected.note}
            </p>
          )}
          {editable && (
            <div className="button-row">
              {selected.suggested && (
                <Button
                  icon={Check}
                  onClick={() => onAction("apply", selected)}
                >
                  Apply
                </Button>
              )}
              {selected.original && (
                <Button
                  icon={PenLine}
                  variant="secondary"
                  onClick={() => onAction("edit", selected)}
                >
                  Edit
                </Button>
              )}
              {selected.decision === "open" && (
                <Button
                  variant="ghost"
                  onClick={() => onAction("dismiss", selected)}
                >
                  Dismiss
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
function Activity({ events }) {
  if (!events.length) return <Empty title="No activity yet" icon={History} />;
  return (
    <ol className="timeline">
      {events.map((event) => (
        <li key={event.id}>
          <span className="timeline-dot" />
          <div>
            <strong>{event.action}</strong>
            <small>
              {event.actor} · {formatDate(event.date, true)}
            </small>
            {event.note && <p>{event.note}</p>}
            {event.sources?.length > 0 && (
              <p>{event.sources.map(sourceLabel).join(", ")}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function DraftScreen({
  draft,
  newDraft,
  role,
  onBack,
  onSave,
  onRecheck,
  onApply,
  onDismiss,
  onSubmit,
  onComment,
  onLegal,
  onApprove,
  onPublish,
  events,
}) {
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState("Findings");
  const [selection, setSelection] = useState("");
  const [dialog, setDialog] = useState(null);
  const [value, setValue] = useState("");
  const [quote, setQuote] = useState("");
  const [version, setVersion] = useState(null);
  const [receiptVersion, setReceiptVersion] = useState(null);
  const manager = role === "manager";
  const editable =
    !manager && ["draft", "changes", "recheck"].includes(draft?.status);
  const reviewable = manager && draft?.status === "review" && draft.checked;
  const blockerCount = draft ? blockers(draft).length : 0;
  const needsLegal = draft?.risk === "High" && !draft.legal;
  const selected =
    draft?.findings.find((item) => item.id === selection) || draft?.findings[0];

  function show(type, item) {
    setValue(type === "edit" ? item.suggested ?? item.original : "");
    setDialog({ type, item });
  }
  function handleAction(type, finding) {
    if (type === "apply") onApply(finding, finding.suggested);
    else show(type, finding);
  }
  function handleDialog(event) {
    event.preventDefault();
    const note = value.trim();
    const { type, item } = dialog;
    if (!note && !["submit", "approve", "publish"].includes(type)) return;
    if (type === "edit") onApply(item, note);
    if (type === "dismiss") onDismiss(item, note);
    if (type === "submit") {
      onSubmit(note);
      setTab("Activity");
    }
    if (type === "comment" || type === "changes") {
      onComment(note, quote, type === "changes");
      setQuote("");
      setTab("Comments");
    }
    if (type === "legal") onLegal(note);
    if (type === "approve" || type === "override") {
      onApprove(draft, note);
      setReceiptVersion(null);
      setTab("Claim Receipt");
    }
    if (type === "publish") onPublish(note);
    setDialog(null);
  }

  if (newDraft || editing)
    return (
      <Editor
        draft={draft}
        onCancel={newDraft ? onBack : () => setEditing(false)}
        onSave={(fields, run) => {
          onSave(fields, run);
          setEditing(false);
          setTab("Findings");
        }}
      />
    );
  if (!draft)
    return (
      <>
        <Button icon={ArrowLeft} variant="ghost" onClick={onBack}>
          Go back
        </Button>
        <Empty
          title="Draft unavailable"
          detail="This draft may be private to the writer or may no longer exist."
        />
      </>
    );

  const tabs = [
    "Findings",
    "Claim Ledger",
    "Comments",
    "Version history",
    "Activity",
    ...(draft.receipt ? ["Claim Receipt"] : []),
  ];
  const active = tabs.includes(tab) ? tab : tabs[0];
  const copyTab = active === "Findings" || active === "Comments";
  const selectedVersion =
    draft.versions.find((item) => item.number === version) ||
    draft.versions.at(-1);
  const receipts = draft.receipt
    ? [draft.receipt, ...(draft.pastReceipts || [])]
    : [];
  const receipt =
    receipts.find((item) => item.version === receiptVersion) || draft.receipt;
  const titles = {
    edit: "Edit the suggested replacement",
    dismiss: "Dismiss finding",
    submit: "Request review",
    comment: "Add comment",
    changes: "Request changes",
    legal: "Record legal sign-off",
    approve: "Approve this version",
    override: "Approve with an override",
    publish: "Record publication",
  };
  const actionLabels = {
    edit: "Apply and re-check",
    dismiss: "Record dismissal",
    submit: "Send to manager",
    comment: "Post comment",
    changes: "Send feedback",
    legal: "Record sign-off",
    approve: "Approve draft",
    override: "Approve with override",
    publish: "Mark published",
  };

  return (
    <>
      <button className="back-link" type="button" onClick={onBack}>
        <ArrowLeft size={16} />{" "}
        {manager ? "Back to review queue" : "Back to my drafts"}
      </button>
      <Header
        eyebrow={manager ? "REVIEW WORKSPACE" : "DRAFT WORKSPACE"}
        title={draft.title}
        description={
          <span className="draft-meta">
            {draft.channel} · Version {draft.version}{" "}
            <Status value={draft.status} /> <Risk value={draft.risk} />
          </span>
        }
        actions={
          editable ? (
            <>
              <Button
                icon={PenLine}
                variant="secondary"
                onClick={() => setEditing(true)}
              >
                Edit draft
              </Button>
              {draft.checked ? (
                <Button icon={Send} onClick={() => show("submit")}>
                  Request review
                </Button>
              ) : (
                <Button
                  icon={Play}
                  onClick={() => {
                    onRecheck(draft);
                    setTab("Findings");
                  }}
                >
                  Run checks
                </Button>
              )}
            </>
          ) : reviewable ? (
            <>
              <Button
                icon={MessageSquare}
                variant="secondary"
                onClick={() => show("changes")}
              >
                Request changes
              </Button>
              {needsLegal ? (
                <Button icon={ShieldCheck} onClick={() => show("legal")}>
                  Record legal sign-off
                </Button>
              ) : (
                <Button
                  icon={ClipboardCheck}
                  onClick={() => show(blockerCount ? "override" : "approve")}
                >
                  {blockerCount ? "Approve with override" : "Approve"}
                </Button>
              )}
            </>
          ) : manager && draft.status === "approved" ? (
            <Button icon={Check} onClick={() => show("publish")}>
              Mark published
            </Button>
          ) : null
        }
      />
      {reviewable && (blockerCount > 0 || draft.risk === "High") && (
        <div className="callout compact">
          <ShieldCheck size={19} />
          <span>
            {needsLegal
              ? "High-risk review requires a recorded legal sign-off. "
              : draft.legal
              ? "Legal sign-off recorded. "
              : ""}
            {blockerCount > 0 &&
              `${blockerCount} unresolved ${
                blockerCount === 1 ? "blocker requires" : "blockers require"
              } a documented override before approval.`}
          </span>
        </div>
      )}
      {draft.status === "recheck" && (
        <div className="callout compact">
          <CircleAlert size={18} /> An approved fact changed. Run checks and
          submit the current version for review.
        </div>
      )}
      {draft.submissionNote && draft.status === "review" && (
        <p className="callout compact">
          <MessageSquare size={17} />
          <span>
            <strong>Writer’s note</strong> {draft.submissionNote}
          </span>
        </p>
      )}
      <Tabs
        items={tabs}
        value={active}
        onChange={setTab}
        label="Draft details"
      />
      <div
        className={
          copyTab || active === "Claim Receipt" || active === "Version history"
            ? "review-grid"
            : "single-panel"
        }
      >
        {copyTab && (
          <DraftText
            draft={draft}
            finding={active === "Findings" ? selected : null}
            onQuote={active === "Comments" ? setQuote : undefined}
          />
        )}
        {active === "Findings" && (
          <FindingPanel
            draft={draft}
            selected={selected}
            onSelect={setSelection}
            onSource={(source) => show("source", source)}
            onAction={handleAction}
            editable={editable && draft.checked}
          />
        )}
        {active === "Claim Ledger" && (
          <section className="card section-card">
            <div className="section-heading">
              <div>
                <h2>Claim Ledger</h2>
                <p>
                  Claims checked against the evidence available for version{" "}
                  {draft.version}.
                </p>
              </div>
            </div>
            {draft.checked ? (
              <Claims
                claims={draft.claims}
                onSource={(source) => show("source", source)}
              />
            ) : (
              <Empty
                title="Run checks to update the ledger"
                icon={FileCheck2}
              />
            )}
          </section>
        )}
        {active === "Comments" && (
          <section className="card section-card">
            <div className="section-heading">
              <div>
                <h2>Comments</h2>
                <p>Select draft text to attach a passage to your comment.</p>
              </div>
              <Button
                variant="secondary"
                icon={MessageSquare}
                onClick={() => show("comment")}
              >
                Add comment
              </Button>
            </div>
            {quote && <p className="callout compact">Selected: “{quote}”</p>}
            {draft.comments.length ? (
              <ul className="comments">
                {draft.comments.map((comment, index) => (
                  <li key={index}>
                    <div>
                      <strong>{comment.author}</strong>
                      <small>{formatDate(comment.date, true)}</small>
                    </div>
                    {comment.quote && <blockquote>{comment.quote}</blockquote>}
                    <p>{comment.text}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty title="No comments yet" icon={MessageSquare} />
            )}
          </section>
        )}
        {active === "Version history" && (
          <>
            <section className="card section-card">
              <div className="section-heading">
                <div>
                  <h2>Version history</h2>
                  <p>Saved edits and checks for this draft.</p>
                </div>
              </div>
              <div className="version-list">
                {[...draft.versions].reverse().map((item) => (
                  <button
                    type="button"
                    key={item.number}
                    className={
                      selectedVersion?.number === item.number
                        ? "version-choice active"
                        : "version-choice"
                    }
                    onClick={() => setVersion(item.number)}
                  >
                    <History size={17} />
                    <span>
                      <strong>Version {item.number}</strong>
                      <small>
                        {item.note} · {formatDate(item.date, true)}
                      </small>
                    </span>
                    <Badge>{item.findings} findings</Badge>
                  </button>
                ))}
              </div>
            </section>
            <section className="card section-card">
              <div className="section-heading">
                <h2>Version {selectedVersion?.number}</h2>
              </div>
              <div className="draft-copy">{selectedVersion?.text}</div>
            </section>
          </>
        )}
        {active === "Activity" && (
          <section className="card section-card">
            <div className="section-heading">
              <h2>Approval history</h2>
            </div>
            <Activity events={events} />
          </section>
        )}
        {active === "Claim Receipt" && (
          <>
            <section className="card section-card">
              <div className="section-heading">
                <div>
                  <h2>Claim Receipt</h2>
                  <p>
                    Evidence recorded when {receipt.approver} approved version{" "}
                    {receipt.version}.
                  </p>
                </div>
                <Badge tone="green">v{receipt.version}</Badge>
              </div>
              {receipts.length > 1 && (
                <div className="toolbar search-toolbar">
                  <select
                    aria-label="Receipt version"
                    value={receipt.version}
                    onChange={(event) =>
                      setReceiptVersion(Number(event.target.value))
                    }
                  >
                    {receipts.map((item) => (
                      <option key={item.version} value={item.version}>
                        Version {item.version} · {formatDate(item.date)}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <Claims
                claims={receipt.claims}
                onSource={(source) => show("source", source)}
              />
              {receipt.override && (
                <p className="callout compact">
                  <strong>Approval override</strong> {receipt.override}
                </p>
              )}
              {receipt.legal && (
                <p className="callout compact">
                  <strong>Legal reference</strong> {receipt.legal}
                </p>
              )}
              {draft.url && /^https?:\/\//i.test(draft.url) && (
                <p className="callout compact">
                  <a href={draft.url} target="_blank" rel="noreferrer">
                    Open published content <ArrowRight size={15} />
                  </a>
                </p>
              )}
            </section>
            <section className="card section-card">
              <div className="section-heading">
                <h2>Approval history</h2>
              </div>
              <Activity
                events={events.filter(
                  (event) =>
                    ![
                      "Ran checks",
                      "Saved draft",
                      "Applied correction",
                    ].includes(event.action)
                )}
              />
            </section>
          </>
        )}
      </div>
      {dialog?.type === "source" && (
        <Modal title={dialog.item.title} onClose={() => setDialog(null)}>
          <div className="modal-body source-modal">
            <Badge tone="teal">{sourceLabel(dialog.item)}</Badge>
            <p>{dialog.item.text}</p>
            <dl>
              <div>
                <dt>Source ID</dt>
                <dd>{dialog.item.id}</dd>
              </div>
              <div>
                <dt>Owner</dt>
                <dd>{dialog.item.owner}</dd>
              </div>
              {dialog.item.expires && (
                <div>
                  <dt>Expires</dt>
                  <dd>{formatDate(dialog.item.expires)}</dd>
                </div>
              )}
            </dl>
          </div>
        </Modal>
      )}
      {dialog && dialog.type !== "source" && (
        <Modal title={titles[dialog.type]} onClose={() => setDialog(null)}>
          <form className="modal-body" onSubmit={handleDialog}>
            {dialog.type === "approve" ? (
              <p>
                Approve version {draft.version} and record the claims and
                evidence in its Claim Receipt.
              </p>
            ) : dialog.type === "publish" ? (
              <Field label="Published URL (optional)">
                <input
                  autoFocus
                  type="url"
                  pattern="https?://.+"
                  value={value}
                  placeholder="https://…"
                  onChange={(event) => setValue(event.target.value)}
                />
              </Field>
            ) : (
              <Field
                label={
                  {
                    submit: "Note for the manager (optional)",
                    legal: "Legal approval reference",
                    edit: "Replacement text",
                    dismiss: "Dismissal reason",
                    override: "Override reason",
                    comment: "Comment",
                    changes: "What should the writer change?",
                  }[dialog.type]
                }
              >
                <textarea
                  autoFocus
                  rows={4}
                  required={dialog.type !== "submit"}
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                />
              </Field>
            )}
            {dialog.type === "override" && (
              <p className="muted">
                {blockerCount} blocker(s) and your reason will be recorded in
                the audit log.
              </p>
            )}
            {dialog.type === "submit" && blockerCount > 0 && (
              <p className="callout compact">
                The manager will see {blockerCount} unresolved blocker(s).
              </p>
            )}
            {["comment", "changes"].includes(dialog.type) && (
              <Field label="Quoted passage (optional)">
                <input
                  value={quote}
                  onChange={(event) => setQuote(event.target.value)}
                />
              </Field>
            )}
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setDialog(null)}>
                Cancel
              </Button>
              <Button type="submit">{actionLabels[dialog.type]}</Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
