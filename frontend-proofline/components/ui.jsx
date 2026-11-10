"use client";

import { useEffect, useRef } from "react";
import { Check, CircleCheck, FileText, X } from "lucide-react";
import { statuses } from "../lib/workflow.mjs";

export function Wordmark() {
  return (
    <span className="wordmark">
      <span className="wordmark-symbol">
        <CircleCheck size={25} strokeWidth={2.2} />
      </span>
      ProofLine<span className="wordmark-dot">.</span>
    </span>
  );
}
export function Button({
  icon: Icon,
  variant = "primary",
  children,
  className = "",
  ...props
}) {
  return (
    <button
      type="button"
      className={`button button-${variant} ${className}`}
      {...props}
    >
      {Icon && <Icon size={16} aria-hidden="true" />}
      {children}
    </button>
  );
}
export function Badge({ children, tone = "neutral" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
const statusTones = {
  review: "amber",
  changes: "red",
  approved: "green",
  published: "green",
  recheck: "amber",
};
export function Status({ value }) {
  return <Badge tone={statusTones[value]}>{statuses[value]}</Badge>;
}
export function Risk({ value }) {
  return (
    <Badge
      tone={value === "High" ? "red" : value === "Medium" ? "amber" : "green"}
    >
      {value} risk
    </Badge>
  );
}
export function Header({ eyebrow, title, description, actions }) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="header-actions">{actions}</div>}
    </header>
  );
}
export function Tabs({ items, value, onChange, label }) {
  return (
    <nav className="tabs" aria-label={label}>
      {items.map((item) => {
        const { key, name } =
          typeof item === "string" ? { key: item, name: item } : item;
        return (
          <button
            type="button"
            key={key}
            className={value === key ? "tab selected" : "tab"}
            aria-current={value === key ? "true" : undefined}
            onClick={() => onChange(key)}
          >
            {name}
          </button>
        );
      })}
    </nav>
  );
}
export function Empty({ title, detail, action, icon: Icon = FileText }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon size={22} />
      </span>
      <h3>{title}</h3>
      {detail && <p>{detail}</p>}
      {action}
    </div>
  );
}
export function Modal({ title, children, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby="modal-title"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="modal-header">
        <h2 id="modal-title">{title}</h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Toast({ children }) {
  return (
    <div className="toast" role="status">
      <Check size={18} />
      {children}
    </div>
  );
}
