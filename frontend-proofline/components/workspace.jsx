"use client";

import { useEffect, useState } from "react";
import {
  Bell,
  BookOpen,
  ChartNoAxesColumn,
  ClipboardCheck,
  FileText,
  House,
  ListChecks,
  LogOut,
  PanelLeft,
} from "lucide-react";
import {
  blockers,
  makeDraft,
  reviewDraft,
  roles,
  seedWorkspace,
  sourceLabel,
  stamp,
  versionOf,
} from "../lib/workflow.mjs";
import {
  checkBackendHealth,
  clearBackendToken,
  loginBackendRole,
  runBackendReview,
  syncBackendDecision,
} from "../lib/backend";
import Login from "./login";
import { Dashboard, DraftList } from "./dashboard";
import { DraftScreen } from "./draft";
import { Alerts, Audit, Insights, Library } from "./governance";
import { Button, Toast, Wordmark } from "./ui";

const workspaceKey = "proofline.workspace.v1";
const roleKey = "proofline.role";
const writerNav = [
  ["home", "Home", House],
  ["drafts", "My drafts", FileText],
  ["library", "Brand library", BookOpen],
];
const managerNav = [
  ["home", "Overview", House],
  ["queue", "Review queue", ClipboardCheck],
  ["library", "Brand library", BookOpen],
  ["insights", "Insights", ChartNoAxesColumn],
  ["alerts", "Alerts", Bell],
  ["audit", "Audit log", ListChecks],
];
const readRoute = () => window.location.hash.slice(1).split("/");
const hasSource = (draft, id) =>
  [...draft.findings, ...draft.claims, ...(draft.receipt?.claims || [])].some(
    (entry) => entry.source.id === id
  );
const evidenceOf = (draft) => [
  ...new Map(
    [...draft.findings, ...draft.claims].map((entry) => [
      entry.source.id,
      entry.source,
    ])
  ).values(),
];

export default function Workspace() {
  const [data, setData] = useState(null);
  const [role, setRole] = useState(null);
  const [route, setRoute] = useState(["home"]);
  const [notice, setNotice] = useState("");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [storageWarning, setStorageWarning] = useState(false);
  const [backendLive, setBackendLive] = useState(false);

  useEffect(() => {
    checkBackendHealth().then(setBackendLive);
    try {
      const saved = localStorage.getItem(workspaceKey);
      setData(saved ? JSON.parse(saved) : seedWorkspace());
      const active = sessionStorage.getItem(roleKey);
      if (Object.hasOwn(roles, active)) setRole(active);
    } catch {
      setData(seedWorkspace());
      setStorageWarning(true);
    }
    const read = () => setRoute(readRoute());
    const refresh = (event) => {
      if (event.key !== workspaceKey || !event.newValue) return;
      try {
        setData(JSON.parse(event.newValue));
      } catch {
        setStorageWarning(true);
      }
    };
    read();
    window.addEventListener("hashchange", read);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("hashchange", read);
      window.removeEventListener("storage", refresh);
    };
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  function go(...parts) {
    window.location.hash = parts.join("/");
    setRoute(parts);
    setMobileOpen(false);
    window.scrollTo(0, 0);
  }
  function changeRole(value) {
    try {
      if (value) {
        sessionStorage.setItem(roleKey, value);
        loginBackendRole(value).then((res) => {
          if (res) setBackendLive(true);
        });
      } else {
        sessionStorage.removeItem(roleKey);
        clearBackendToken();
      }
    } catch {
      setStorageWarning(true);
    }
    setRole(value);
    go("home");
  }
  async function enrichWithLiveAI(savedDraft) {
    if (!backendLive) return;
    try {
      const remote = await runBackendReview(savedDraft);
      setData((prev) => {
        if (!prev) return prev;
        const nextDrafts = prev.drafts.map((item) => {
          if (item.id !== savedDraft.id) return item;
          const existingKeys = new Set(
            item.findings.map((f) => `${f.original.toLowerCase()}::${f.source?.id}`)
          );
          const extraFindings = remote.findings.filter(
            (f) =>
              f.original &&
              !existingKeys.has(`${f.original.toLowerCase()}::${f.source?.id}`)
          );
          const mergedFindings = [...item.findings, ...extraFindings];

          const existingClaimTexts = new Set(
            item.claims.map((c) => c.text.toLowerCase())
          );
          const extraClaims = remote.claims.filter(
            (c) => c.text && !existingClaimTexts.has(c.text.toLowerCase())
          );
          const mergedClaims = [...item.claims, ...extraClaims];

          const hasBlocker = mergedFindings.some(
            (f) => f.severity === "Blocker" && f.decision === "open"
          );
          const hasWarning = mergedFindings.some(
            (f) => f.severity === "Warning" && f.decision === "open"
          );
          const nextRisk = hasBlocker
            ? "High"
            : hasWarning && item.risk === "Low"
            ? "Medium"
            : item.risk;

          return {
            ...item,
            backendId: remote.backendId,
            findings: mergedFindings,
            claims: mergedClaims,
            risk: nextRisk,
          };
        });
        const nextState = { ...prev, drafts: nextDrafts };
        try {
          localStorage.setItem(workspaceKey, JSON.stringify(nextState));
        } catch {}
        return nextState;
      });
      if (remote.findings.length > 0) {
        setNotice(`Groq AI backend check synced (${remote.findings.length} AI finding(s))`);
      }
    } catch (err) {
      console.warn("Live backend review skipped:", err);
    }
  }
  function commit(next, message) {
    setData(next);
    try {
      localStorage.setItem(workspaceKey, JSON.stringify(next));
    } catch {
      setStorageWarning(true);
    }
    if (message) setNotice(message);
  }
  function addEvent(workspace, action, detail, fields = {}) {
    return {
      ...workspace,
      events: [
        {
          id: crypto.randomUUID(),
          actor: roles[role],
          action,
          detail,
          date: stamp(),
          ...fields,
        },
        ...workspace.events,
      ],
    };
  }
  function saveDraft(draft, action, message, metadata) {
    const updated = { ...draft, updated: stamp() };
    const exists = data.drafts.some((item) => item.id === draft.id);
    const drafts = exists
      ? data.drafts.map((item) => (item.id === draft.id ? updated : item))
      : [updated, ...data.drafts];
    const next = { ...data, drafts };
    commit(
      action
        ? addEvent(next, action, draft.title, {
            draftId: draft.id,
            ...metadata,
          })
        : next,
      message
    );
    return updated;
  }
  function runChecks(
    draft,
    note = "Ran content checks",
    previousFindings = draft.findings
  ) {
    const checked = reviewDraft(draft, data.sources);
    // Retain decisions only when the cited version and original excerpt still match.
    const findings = checked.findings.map((finding) => {
      const previous = previousFindings.find(
        (item) =>
          item.id === finding.id &&
          item.original === finding.original &&
          item.source.version === finding.source.version &&
          item.decision === "dismissed"
      );
      return previous
        ? { ...finding, decision: previous.decision, note: previous.note }
        : finding;
    });
    const next = {
      ...draft,
      ...checked,
      findings,
      checked: true,
      version: draft.version + 1,
      legal: "",
    };
    next.versions = [...draft.versions, versionOf(next, note)];
    return next;
  }
  function saveSource(values, existing) {
    const entry = {
      ...values,
      id:
        existing?.id || `SRC-${crypto.randomUUID().slice(0, 8).toUpperCase()}`,
      version: (existing?.version || 0) + 1,
    };
    const sourceList = existing
      ? data.sources.map((source) => (source.id === entry.id ? entry : source))
      : [entry, ...data.sources];
    let next = { ...data, sources: sourceList };
    if (existing?.type === "Approved facts") {
      const affected = data.drafts.filter((draft) =>
        hasSource(draft, existing.id)
      );
      if (affected.length) {
        const ids = new Set(affected.map((draft) => draft.id));
        const alert = {
          id: crypto.randomUUID(),
          source: entry,
          previous: existing,
          date: stamp(),
          resolved: false,
          affected: affected.map(({ id, title, status }) => ({
            id,
            title,
            status,
          })),
        };
        next = {
          ...next,
          alerts: [alert, ...data.alerts],
          drafts: data.drafts.map((draft) =>
            ids.has(draft.id) && draft.status !== "published"
              ? {
                  ...draft,
                  status: "recheck",
                  checked: false,
                  legal: "",
                  updated: stamp(),
                }
              : draft
          ),
        };
      }
    }
    commit(
      addEvent(
        next,
        existing ? "Updated source" : "Added source",
        `${entry.title} · v${entry.version}`,
        { sourceId: entry.id }
      ),
      `${sourceLabel(entry)} saved`
    );
  }
  function approve(draft, override) {
    if (
      draft.status !== "review" ||
      !draft.checked ||
      (blockers(draft).length && !override) ||
      (draft.risk === "High" && !draft.legal)
    )
      return;
    const receipt = {
      version: draft.version,
      claims: draft.claims,
      date: stamp(),
      approver: roles[role],
      legal: draft.legal,
      override,
    };
    const pastReceipts = draft.receipt
      ? [draft.receipt, ...(draft.pastReceipts || [])]
      : [];
    saveDraft(
      { ...draft, status: "approved", receipt, pastReceipts },
      override ? "Approved with override" : "Approved draft",
      "Approved and Claim Receipt recorded",
      {
        note: override,
        sources: evidenceOf(draft),
        overrideSources: blockers(draft).map((item) => item.source.id),
      }
    );
    syncBackendDecision(draft.backendId, "approved", override || draft.legal);
  }

  if (!data)
    return (
      <main className="loading">
        <Wordmark />
        <p>Opening your workspace…</p>
      </main>
    );
  if (!role) return <Login onLogin={changeRole} />;

  const navigation = role === "writer" ? writerNav : managerNav;
  const [page, id] = route;
  const candidate = data.drafts.find((item) => item.id === id);
  const draft =
    role === "manager" && candidate?.status === "draft" ? null : candidate;
  const allowed = page === "draft" || navigation.some(([key]) => key === page);
  const activePage = allowed && page ? page : "home";
  const activeNav =
    activePage === "draft"
      ? role === "writer"
        ? "drafts"
        : "queue"
      : activePage;
  const startDraft = () => go("draft", "new");
  const openDraft = (value) => go("draft", value);
  let content;

  switch (activePage) {
    case "draft":
      content = (
        <DraftScreen
          key={id}
          draft={draft}
          newDraft={id === "new" && role === "writer"}
          role={role}
          onBack={() => go(activeNav)}
          events={data.events.filter((event) => event.draftId === id)}
          onApprove={approve}
          onSave={(fields, run) => {
            const base = draft || makeDraft({});
            let next = { ...base, ...fields, checked: false };
            if (run) next = runChecks(next);
            else {
              next = {
                ...next,
                findings: [],
                claims: [],
                risk: "Low",
                legal: "",
                version: base.version + 1,
              };
              next.versions = [
                ...base.versions,
                versionOf(next, "Saved draft"),
              ];
            }
            const saved = saveDraft(
              next,
              run ? "Ran checks" : "Saved draft",
              run ? "Content checks complete" : "Draft saved",
              run ? { sources: evidenceOf(next) } : undefined
            );
            if (run) enrichWithLiveAI(saved);
            if (!draft) openDraft(saved.id);
            return saved;
          }}
          onRecheck={(target) => {
            const checked = runChecks(target);
            const saved = saveDraft(checked, "Ran checks", "Content checks complete", {
              sources: evidenceOf(checked),
            });
            enrichWithLiveAI(saved);
          }}
          onApply={(finding, replacement) => {
            if (
              draft.text.slice(
                finding.start,
                finding.start + finding.original.length
              ) !== finding.original
            )
              return;
            const text =
              draft.text.slice(0, finding.start) +
              replacement +
              draft.text.slice(finding.start + finding.original.length);
            saveDraft(
              runChecks({ ...draft, text }, "Edited and re-checked"),
              "Applied correction",
              "Correction applied and draft re-checked",
              { sourceId: finding.source.id, sources: [finding.source] }
            );
          }}
          onDismiss={(finding, note) =>
            saveDraft(
              {
                ...draft,
                findings: draft.findings.map((item) =>
                  item.id === finding.id
                    ? { ...item, decision: "dismissed", note }
                    : item
                ),
              },
              "Dismissed finding",
              "Dismissal recorded",
              { sourceId: finding.source.id, sources: [finding.source], note }
            )
          }
          onSubmit={(note) =>
            saveDraft(
              { ...draft, status: "review", submissionNote: note, legal: "" },
              "Requested review",
              "Draft sent to the manager",
              { note }
            )
          }
          onComment={(note, quote, changes) => {
            const comments = [
              ...draft.comments,
              { author: roles[role], text: note, quote, date: stamp() },
            ];
            saveDraft(
              {
                ...draft,
                comments,
                ...(changes ? { status: "changes", legal: "" } : {}),
              },
              changes ? "Requested changes" : "Added comment",
              changes ? "Changes requested" : "Comment added",
              { note }
            );
          }}
          onLegal={(reference) =>
            saveDraft(
              { ...draft, legal: reference },
              "Recorded legal sign-off",
              "Legal sign-off recorded",
              { note: reference }
            )
          }
          onPublish={(url) =>
            saveDraft(
              { ...draft, status: "published", url },
              "Marked published",
              "Publication recorded",
              { note: url }
            )
          }
        />
      );
      break;
    case "drafts":
    case "queue":
      content = (
        <DraftList
          drafts={data.drafts}
          role={role}
          onOpen={openDraft}
          onNew={startDraft}
        />
      );
      break;
    case "library":
      content = (
        <Library sources={data.sources} role={role} onSave={saveSource} />
      );
      break;
    case "insights":
      content = (
        <Insights
          data={data}
          onAlerts={() => go("alerts")}
          onLibrary={() => go("library")}
        />
      );
      break;
    case "alerts":
      content = (
        <Alerts
          alerts={data.alerts}
          onOpen={openDraft}
          onResolve={(alert) => {
            const alerts = data.alerts.map((item) =>
              item.id === alert.id ? { ...item, resolved: true } : item
            );
            commit(
              addEvent(
                { ...data, alerts },
                "Acknowledged fact change",
                alert.source.title,
                { sourceId: alert.source.id }
              ),
              "Alert acknowledged"
            );
          }}
        />
      );
      break;
    case "audit":
      content = <Audit events={data.events} onOpen={openDraft} />;
      break;
    default:
      content = (
        <Dashboard
          data={data}
          role={role}
          onOpen={openDraft}
          onNew={startDraft}
          onList={() =>
            go(activeNav === "home" && role === "manager" ? "queue" : "drafts")
          }
        />
      );
  }

  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main").focus();
        }}
      >
        Skip to content
      </a>
      <div className="mobile-bar">
        <Wordmark />
        <Button
          variant="ghost"
          icon={PanelLeft}
          aria-expanded={mobileOpen}
          aria-controls="sidebar"
          onClick={() => setMobileOpen(!mobileOpen)}
        >
          Menu
        </Button>
      </div>
      <aside
        id="sidebar"
        className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}
      >
        <a href="#home" className="sidebar-logo" onClick={() => go("home")}>
          <Wordmark />
        </a>
        <div className="workspace-label">
          <span className="workspace-avatar">SN</span>
          <span>
            <strong>Studio North</strong>
            <small>Brand workspace</small>
          </span>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav className="sidebar-links" aria-label="Main navigation">
          {navigation.map(([key, label, Icon]) => (
            <a
              href={`#${key}`}
              key={key}
              aria-current={activeNav === key ? "page" : undefined}
              className={activeNav === key ? "active" : ""}
              onClick={() => go(key)}
            >
              <Icon size={18} />
              {label}
              {key === "alerts" &&
                data.alerts.some((alert) => !alert.resolved) && (
                  <span className="nav-dot" />
                )}
            </a>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div>
            <span className="profile-initial">
              {role === "writer" ? "CW" : "M"}
            </span>
            <span>
              <strong>{roles[role]}</strong>
              <small>{backendLive ? "Connected · Groq API" : "Local demo mode"}</small>
            </span>
          </div>
          <button
            type="button"
            className="icon-button"
            aria-label="Sign out"
            title="Sign out"
            onClick={() => changeRole(null)}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <main id="main" tabIndex={-1} className="main">
        <div className="page">
          {storageWarning && (
            <p className="callout">
              Browser storage is unavailable. Changes last for this session.
            </p>
          )}
          {content}
        </div>
      </main>
      {notice && <Toast>{notice}</Toast>}
    </div>
  );
}
