"use client";

import { useState } from "react";
import {
  ArrowRight,
  Bell,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  FileText,
  MessageSquare,
  PenLine,
  Plus,
  Search,
  ShieldAlert,
} from "lucide-react";
import { formatDate } from "../lib/workflow.mjs";
import { Badge, Button, Empty, Header, Risk, Status, Tabs } from "./ui";

function DraftTable({ drafts, role, onOpen }) {
  if (!drafts.length)
    return (
      <Empty
        title="No matching drafts"
        detail="Try a different filter or search term."
      />
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Draft</th>
            <th>Status</th>
            {role === "manager" && <th>Risk</th>}
            <th>Last updated</th>
            <th>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {drafts.map((draft) => (
            <tr key={draft.id}>
              <td>
                <a
                  className="document-link"
                  href={`#draft/${draft.id}`}
                  onClick={(event) => {
                    event.preventDefault();
                    onOpen(draft.id);
                  }}
                >
                  <span className="file-icon">
                    <FileText size={18} />
                  </span>
                  <span>
                    <strong>{draft.title}</strong>
                    <small>
                      {draft.channel} · v{draft.version}
                    </small>
                  </span>
                </a>
              </td>
              <td>
                <Status value={draft.status} />
                {role === "manager" &&
                  draft.status === "review" &&
                  draft.risk === "High" && (
                    <small className="table-subtle">
                      {draft.legal
                        ? "Legal sign-off recorded"
                        : "Legal sign-off required"}
                    </small>
                  )}
              </td>
              {role === "manager" && (
                <td>
                  <Risk value={draft.risk} />
                </td>
              )}
              <td className="muted">{formatDate(draft.updated)}</td>
              <td>
                <button
                  className="icon-button row-arrow"
                  type="button"
                  aria-label={`Open ${draft.title}`}
                  onClick={() => onOpen(draft.id)}
                >
                  <ArrowRight size={18} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Dashboard({ data, role, onOpen, onNew, onList }) {
  const manager = role === "manager";
  const drafts = data.drafts.filter(
    (draft) => !manager || draft.status !== "draft"
  );
  const count = (...statuses) =>
    drafts.filter((draft) => statuses.includes(draft.status)).length;
  const metrics = manager
    ? [
        ["Awaiting review", count("review"), ClipboardCheck, "teal"],
        [
          "High-risk reviews",
          drafts.filter(
            (draft) => draft.risk === "High" && draft.status === "review"
          ).length,
          ShieldAlert,
          "amber",
        ],
        [
          "Open alerts",
          data.alerts.filter((alert) => !alert.resolved).length,
          Bell,
          "teal",
        ],
      ]
    : [
        ["In progress", count("draft", "changes", "recheck"), PenLine, "teal"],
        ["In review", count("review"), Clock3, "amber"],
        ["Approved", count("approved", "published"), CheckCircle2, "teal"],
      ];
  const recent = [...drafts].sort((a, b) => b.updated.localeCompare(a.updated));
  const feedbackDraft = recent.find(
    (draft) => draft.status === "changes" && draft.comments.length
  );

  return (
    <>
      <Header
        eyebrow={manager ? "MANAGER WORKSPACE" : "WRITER WORKSPACE"}
        title={manager ? "Workspace overview" : "My workspace"}
        description={
          manager
            ? "Review content, track risk, and keep your brand sources current."
            : "Draft, check, and send your content for review."
        }
        actions={
          manager ? (
            <Button icon={ClipboardCheck} onClick={onList}>
              Review queue
            </Button>
          ) : (
            <Button icon={Plus} onClick={onNew}>
              New draft
            </Button>
          )
        }
      />
      <div className="metrics">
        {metrics.map(([name, value, Icon, tone]) => (
          <div className="card metric" key={name}>
            <span className={`metric-icon metric-${tone}`}>
              <Icon size={20} />
            </span>
            <div>
              <p>{name}</p>
              <strong>{value}</strong>
            </div>
          </div>
        ))}
      </div>
      <section className="card section-card">
        <div className="section-heading">
          <div>
            <h2>{manager ? "Recent submissions" : "My drafts"}</h2>
            <p>
              {manager
                ? "Drafts moving through the approval workflow."
                : "Pick up where you left off."}
            </p>
          </div>
          <Button variant="ghost" onClick={onList}>
            View all <ArrowRight size={15} />
          </Button>
        </div>
        <DraftTable drafts={recent.slice(0, 5)} role={role} onOpen={onOpen} />
      </section>
      {!manager && feedbackDraft && (
        <div className="callout feedback">
          <MessageSquare size={20} />
          <div>
            <strong>Manager feedback</strong>
            <p>{feedbackDraft.comments.at(-1).text}</p>
          </div>
          <Button variant="ghost" onClick={() => onOpen(feedbackDraft.id)}>
            Open draft <ArrowRight size={16} />
          </Button>
        </div>
      )}
    </>
  );
}
export function DraftList({ drafts, role, onOpen, onNew }) {
  const manager = role === "manager";
  const [filter, setFilter] = useState(manager ? "review" : "all");
  const [query, setQuery] = useState("");
  const [risk, setRisk] = useState("");
  const pool = drafts.filter((draft) => !manager || draft.status !== "draft");
  const filters = manager
    ? [
        ["review", "Awaiting review"],
        ["changes", "Changes requested"],
        ["approved", "Approved"],
        ["recheck", "Needs re-check"],
        ["all", "All"],
      ]
    : [
        ["all", "All drafts"],
        ["draft", "In progress"],
        ["review", "In review"],
        ["changes", "Changes requested"],
        ["approved", "Approved"],
        ["recheck", "Needs re-check"],
      ];
  const matches = (draft, key) =>
    key === "all" ||
    draft.status === key ||
    (key === "approved" && draft.status === "published");
  const visible = pool
    .filter(
      (draft) =>
        matches(draft, filter) &&
        (!risk || draft.risk === risk) &&
        `${draft.title} ${draft.channel}`
          .toLowerCase()
          .includes(query.trim().toLowerCase())
    )
    .sort((a, b) => b.updated.localeCompare(a.updated));
  return (
    <>
      <Header
        eyebrow={manager ? "APPROVAL WORKFLOW" : "WRITER WORKSPACE"}
        title={manager ? "Review queue" : "My drafts"}
        description={
          manager
            ? "Inspect evidence, send feedback, and make approval decisions."
            : "Find and manage drafts at every stage."
        }
        actions={
          !manager && (
            <Button icon={Plus} onClick={onNew}>
              New draft
            </Button>
          )
        }
      />
      <section className="card section-card">
        <div className="toolbar">
          <Tabs
            label="Draft status"
            items={filters.map(([key, name]) => ({
              key,
              name: (
                <>
                  {name}{" "}
                  <Badge>
                    {pool.filter((draft) => matches(draft, key)).length}
                  </Badge>
                </>
              ),
            }))}
            value={filter}
            onChange={setFilter}
          />
        </div>
        <div className="toolbar search-toolbar">
          <label className="search">
            <Search size={17} />
            <input
              aria-label="Search drafts"
              placeholder="Search drafts…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          {manager && (
            <select
              aria-label="Risk level"
              value={risk}
              onChange={(event) => setRisk(event.target.value)}
            >
              <option value="">All risk levels</option>
              <option>High</option>
              <option>Medium</option>
              <option>Low</option>
            </select>
          )}
        </div>
        <DraftTable drafts={visible} role={role} onOpen={onOpen} />
      </section>
    </>
  );
}
