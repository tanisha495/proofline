"use client";

import { useState } from "react";
import {
  ArrowRight,
  ClipboardCheck,
  Eye,
  EyeOff,
  FileCheck2,
  PenLine,
  ShieldCheck,
  Users,
} from "lucide-react";
import { roles } from "../lib/workflow.mjs";
import { Badge, Button, Field, Wordmark } from "./ui";

const demoUsers = {
  writer: "writer@studionorth.demo",
  manager: "manager@studionorth.demo",
};

export default function Login({ onLogin }) {
  const [role, setRole] = useState("writer");
  const [email, setEmail] = useState(demoUsers.writer);
  const [password, setPassword] = useState("proofline-demo");
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState("");
  function selectRole(value) {
    setRole(value);
    setEmail(demoUsers[value]);
    setPassword("proofline-demo");
    setError("");
  }
  return (
    <main className="login">
      <section className="login-story">
        <Wordmark />
        <div className="login-story-content">
          <p className="eyebrow">
            <span className="signal" /> Pre-publication review
          </p>
          <h1>
            Check it before
            <br />
            you publish it<span>.</span>
          </h1>
          <p className="login-tagline">
            A shared workspace for better drafts, evidence-backed feedback, and
            approvals you can trace.
          </p>
          <div className="login-steps">
            {[
              ["Draft", PenLine],
              ["Evidence", FileCheck2],
              ["Approval", ShieldCheck],
            ].map(([name, Icon]) => (
              <div className="login-step" key={name}>
                <span>
                  <Icon size={23} strokeWidth={1.7} />
                </span>
                {name}
              </div>
            ))}
          </div>
        </div>
        <p className="login-story-footer">
          <span>ProofLine</span>
          <span>Brand review workspace</span>
        </p>
      </section>
      <section className="login-panel">
        <form
          className="login-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (
              email.trim().toLowerCase() !== demoUsers[role] ||
              password !== "proofline-demo"
            ) {
              setError(
                "Use the demo credentials for this role. Select the role again to refill them."
              );
              return;
            }
            onLogin(role);
          }}
        >
          <Badge tone="teal">Demo workspace</Badge>
          <h2>Sign in to ProofLine</h2>
          <p className="muted">Choose how you’ll work in Studio North.</p>
          <fieldset className="login-roles">
            <legend className="sr-only">Workspace role</legend>
            {[
              ["writer", PenLine, "Create and check drafts"],
              ["manager", Users, "Review and manage standards"],
            ].map(([value, Icon, description]) => (
              <label
                key={value}
                className={`login-role ${role === value ? "active" : ""}`}
              >
                <input
                  type="radio"
                  name="role"
                  checked={role === value}
                  onChange={() => selectRole(value)}
                  onClick={() => {
                    if (role === value) selectRole(value);
                  }}
                />
                <Icon size={22} />
                <span>
                  <strong>{roles[value]}</strong>
                  <small>{description}</small>
                </span>
              </label>
            ))}
          </fieldset>
          <Field label="Work email">
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </Field>
          <Field label="Password">
            <span className="password-field">
              <input
                type={visible ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                type="button"
                className="icon-button"
                aria-label={visible ? "Hide password" : "Show password"}
                onClick={() => setVisible(!visible)}
              >
                {visible ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </span>
          </Field>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <Button type="submit" className="login-submit">
            Sign in as {roles[role]} <ArrowRight size={17} />
          </Button>
          <p className="demo-note">
            <ClipboardCheck size={16} /> Demo credentials are filled in for each
            role.
          </p>
        </form>
      </section>
    </main>
  );
}
