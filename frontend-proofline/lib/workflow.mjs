export const roles = { writer: "Content Writer", manager: "Manager" };
export const statuses = {
  draft: "In progress",
  review: "In review",
  changes: "Changes requested",
  approved: "Approved",
  published: "Published",
  recheck: "Needs re-check",
};
export const channels = [
  "Email",
  "Social post",
  "Website",
  "Press release",
  "Advertisement",
  "Document",
];
export const libraryTabs = [
  "Guidelines",
  "Approved facts",
  "Terminology",
  "Assets",
];
export const emptyIntent = { message: "", audience: "", action: "" };
export const emptyVisual = { foreground: "", background: "" };

const sources = [
  {
    id: "FACT-001",
    type: "Approved facts",
    title: "Starter plan pricing",
    source: "Pricing Sheet",
    owner: "Product",
    version: 3,
    value: "1299",
    text: "The Starter plan costs ₹1,299 per month.",
    expires: "2027-12-31",
    keyword: "Starter plan",
  },
  {
    id: "FACT-002",
    type: "Approved facts",
    title: "Starter plan features",
    source: "Product Reference",
    owner: "Product",
    version: 2,
    text: "The Starter plan includes five projects and email support.",
    expires: "2027-12-31",
  },
  {
    id: "RULE-014",
    type: "Guidelines",
    check: "claim",
    title: "Substantiate promotional claims",
    source: "Claims Policy",
    owner: "Legal",
    version: 2,
    text: "Superlatives and guaranteed outcomes require approved evidence. Use specific, verifiable language when evidence is unavailable.",
  },
  {
    id: "RULE-018",
    type: "Guidelines",
    check: "tone",
    title: "Keep language clear and measured",
    source: "Brand Voice",
    owner: "Brand",
    version: 1,
    text: "Avoid pressure and hype. Use direct language that lets readers make an informed choice.",
  },
  {
    id: "RULE-021",
    type: "Guidelines",
    check: "alt",
    title: "Describe meaningful images",
    source: "Accessibility Checklist",
    owner: "Design",
    version: 2,
    text: "Include a brief text alternative for meaningful images in published content.",
  },
  {
    id: "RULE-025",
    type: "Guidelines",
    check: "disclaimer",
    title: "Include promotional terms",
    source: "Promotions Guide",
    owner: "Legal",
    version: 1,
    text: "Advertisements that present a discount or offer must include “Terms apply.”",
  },
  {
    id: "RULE-027",
    type: "Guidelines",
    check: "contrast",
    title: "Keep body text legible",
    source: "Accessibility Checklist",
    owner: "Design",
    version: 2,
    text: "Normal-sized text needs at least a 4.5:1 contrast ratio against its background.",
  },
  {
    id: "TERM-004",
    type: "Terminology",
    title: "Use the approved plan name",
    source: "Terminology Guide",
    owner: "Brand",
    version: 1,
    keyword: "Starter Pack",
    value: "Starter plan",
    text: "Use “Starter plan” in customer-facing content.",
  },
  {
    id: "ASSET-001",
    type: "Assets",
    title: "Primary wordmark",
    source: "Visual Identity Guide",
    owner: "Design",
    version: 2,
    text: "Approved navy wordmark for light backgrounds.",
  },
];

export function money(value) {
  return `₹${Number(value).toLocaleString("en-IN")}`;
}
export function sourceLabel(source) {
  return `${source.source} · v${source.version}`;
}
export function stamp() {
  return new Date().toISOString();
}
export function formatDate(date, includeTime = false) {
  if (!date) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    ...(includeTime
      ? { hour: "numeric", minute: "2-digit" }
      : { year: "numeric" }),
  }).format(new Date(date.length === 10 ? `${date}T00:00:00` : date));
}
export function isExpired(source) {
  return Boolean(
    source.expires && new Date(`${source.expires}T23:59:59`) < new Date()
  );
}
function luminance(hex) {
  const channels = hex
    .slice(1)
    .match(/../g)
    .map((pair) => {
      const value = parseInt(pair, 16) / 255;
      return value <= 0.04045
        ? value / 12.92
        : ((value + 0.055) / 1.055) ** 2.4;
    });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}
export function reviewDraft(
  { text, channel, intent = emptyIntent, visual = emptyVisual },
  library
) {
  const findings = [];
  const claims = [];
  function flag(match, source, title, severity, reason, suggested) {
    const finding = {
      id: `${source.id}-${match.index}`,
      start: match.index,
      original: match[0],
      source: { ...source },
      title,
      severity,
      reason,
      suggested,
      confidence: "High",
      decision: "open",
      note: "",
    };
    findings.push(finding);
  }
  for (const source of library) {
    if (source.type === "Approved facts" && source.value && source.keyword) {
      for (const match of text.matchAll(/₹\s*(\d+(?:,\d+)*(?:\.\d+)?)/g)) {
        const lineStart =
          Math.max(
            text.lastIndexOf("\n", match.index),
            text.lastIndexOf(".", match.index)
          ) + 1;
        const prefix = text.slice(lineStart, match.index).toLowerCase();
        if (!prefix.includes(source.keyword.toLowerCase())) continue;
        const expired = isExpired(source);
        const supported =
          Number(match[1].replaceAll(",", "")) === Number(source.value);
        const qualifier = /\b(starting (?:at|from)|up to|as low as)\s*$/i.exec(
          prefix
        )?.[1];
        const qualified = Boolean(qualifier);
        const status = expired
          ? "Expired evidence"
          : qualified
          ? "Needs a human"
          : supported
          ? "Supported"
          : "Conflicts";
        claims.push({
          text: `${source.keyword} ${qualifier || "costs"} ${match[0]}`,
          status,
          source: { ...source },
        });
        if (expired)
          flag(
            match,
            source,
            "Pricing evidence has expired",
            "Blocker",
            "The fact owner needs to renew this evidence before the price can be verified.",
            null
          );
        else if (qualified)
          flag(
            match,
            source,
            "Check qualified pricing",
            "Warning",
            "A reviewer should confirm that the price qualifier is supported by the approved evidence.",
            null
          );
        else if (!supported)
          flag(
            match,
            source,
            "Price conflicts with approved fact",
            "Blocker",
            `The current approved price for the ${source.keyword} is ${money(
              source.value
            )}.`,
            money(source.value)
          );
      }
    }
    if (source.type === "Terminology" && source.keyword && source.value) {
      const escaped = source.keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      for (const match of text.matchAll(new RegExp(`\\b${escaped}\\b`, "gi"))) {
        flag(
          match,
          source,
          "Use approved terminology",
          "Warning",
          source.text,
          source.value
        );
      }
    }
    if (source.type !== "Guidelines") continue;
    if (source.check === "claim") {
      for (const match of text.matchAll(
        /(?:\b(?:guaranteed results|the best|number one|risk-free)|#1)\b/gi
      )) {
        claims.push({
          text: match[0],
          status: "Unsupported",
          source: { ...source },
          policy: true,
        });
        flag(
          match,
          source,
          "Promotional claim needs evidence",
          "Blocker",
          "The claims policy requires approved evidence for this wording.",
          null
        );
      }
    }
    if (source.check === "tone") {
      for (const match of text.matchAll(
        /\b(?:act now or miss out|insanely good|hurry up)\b/gi
      )) {
        flag(
          match,
          source,
          "Use more measured language",
          "Warning",
          source.text,
          "Explore the offer"
        );
      }
    }
    if (source.check === "alt") {
      for (const match of text.matchAll(/!\[\]\([^)]+\)/g)) {
        flag(
          match,
          source,
          "Image is missing alt text",
          "Warning",
          source.text,
          null
        );
      }
    }
    if (
      source.check === "disclaimer" &&
      channel === "Advertisement" &&
      !/terms apply/i.test(text)
    ) {
      const offer = /\b(?:discount|offer|\d+% off)\b/i.exec(text);
      if (offer)
        flag(
          offer,
          source,
          "Promotional terms are missing",
          "Warning",
          source.text,
          null
        );
    }
    if (
      source.check === "contrast" &&
      [visual.foreground, visual.background].every((color) =>
        /^#[\da-f]{6}$/i.test(color)
      )
    ) {
      const lightness = [
        luminance(visual.foreground),
        luminance(visual.background),
      ].sort((a, b) => b - a);
      const ratio = (lightness[0] + 0.05) / (lightness[1] + 0.05);
      if (ratio < 4.5)
        flag(
          { 0: "", index: -1 },
          source,
          "Text contrast is too low",
          "Warning",
          `This color pair has a ${ratio.toFixed(
            2
          )}:1 contrast ratio. Choose a pair that meets 4.5:1.`,
          null
        );
    }
  }
  return {
    findings: findings.sort(
      (a, b) =>
        (a.severity === "Blocker" ? 0 : 1) -
          (b.severity === "Blocker" ? 0 : 1) || a.start - b.start
    ),
    claims,
    risk: claims.length ? "High" : findings.length ? "Medium" : "Low",
    intentRecorded: Object.values(intent).some(Boolean),
  };
}
export function blockers(draft) {
  return draft.findings.filter(
    (finding) =>
      finding.severity === "Blocker" && finding.decision !== "resolved"
  );
}
export function versionOf(draft, note) {
  return {
    number: draft.version,
    text: draft.text,
    findings: draft.findings.length,
    date: stamp(),
    note,
  };
}
export function makeDraft(fields) {
  return {
    id: crypto.randomUUID(),
    title: "",
    text: "",
    channel: "Email",
    intent: { ...emptyIntent },
    visual: { ...emptyVisual },
    attachment: "",
    status: "draft",
    version: 0,
    versions: [],
    checked: false,
    findings: [],
    claims: [],
    risk: "Low",
    comments: [],
    receipt: null,
    legal: "",
    updated: stamp(),
    ...fields,
  };
}
export function seedWorkspace() {
  const samples = [
    {
      id: "summer-launch",
      title: "Summer launch email",
      text: "Hi there,\n\nGet the Starter plan for ₹999 per month.\nExplore the summer offer and sign up today.",
      status: "changes",
      intent: {
        message: "Introduce the Starter plan and summer offer",
        audience: "New and existing subscribers",
        action: "Sign up for the Starter plan",
      },
      comments: [
        {
          author: "Manager",
          text: "Please update the price from ₹999 to ₹1,299 using Pricing Sheet · v3.",
          quote: "Get the Starter plan for ₹999 per month.",
          date: "2026-11-09T09:00:00Z",
        },
      ],
    },
    {
      id: "product-refresh",
      title: "Product page refresh",
      text: "The Starter plan costs ₹1,299 per month. Explore what’s included.",
      status: "review",
      channel: "Website",
    },
    {
      id: "launch-announcement",
      title: "Launch announcement",
      text: "Introducing the Starter plan for ₹1,299 per month.",
      status: "published",
      channel: "Social post",
    },
    {
      id: "november-newsletter",
      title: "November newsletter",
      text: "Explore what’s new this month.",
      status: "draft",
    },
  ];
  const drafts = samples.map((sample) => {
    const draft = makeDraft({
      ...sample,
      updated: "2026-11-09T09:00:00Z",
      version: 1,
    });
    Object.assign(draft, reviewDraft(draft, sources), {
      checked: sample.status !== "draft",
    });
    draft.versions = [
      { ...versionOf(draft, "Initial version"), date: draft.updated },
    ];
    if (sample.status === "published") {
      draft.receipt = {
        version: 1,
        claims: draft.claims,
        date: draft.updated,
        legal: "Demo legal approval LA-104",
        approver: "Manager",
        override: "",
      };
    }
    return draft;
  });
  return {
    sources,
    drafts,
    alerts: [],
    events: [
      {
        id: "seed-3",
        draftId: "summer-launch",
        actor: "Manager",
        action: "Requested changes",
        detail: "Summer launch email",
        date: "2026-11-09T09:00:00Z",
      },
      {
        id: "seed-2",
        draftId: "product-refresh",
        actor: "Content Writer",
        action: "Requested review",
        detail: "Product page refresh",
        date: "2026-11-09T08:00:00Z",
      },
      {
        id: "seed-1",
        draftId: "launch-announcement",
        actor: "Manager",
        action: "Marked published",
        detail: "Launch announcement",
        date: "2026-11-08T09:00:00Z",
      },
    ],
  };
}
