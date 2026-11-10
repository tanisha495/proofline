import type { Finding } from "@/types/finding";

export const mockFindings: Finding[] = [
  {
    id: "f-001",
    draft_id: "d-001",
    version_id: "v-001",
    quoted_text: "Our coffee is the healthiest beverage on the market",
    start: 42,
    end: 93,
    severity: "blocker",
    reason:
      "Unsubstantiated superlative health claim. Guideline TONE-01 prohibits absolute health claims without peer-reviewed citations.",
    source_ref: "TONE-01",
    source_version: 1,
    confidence: "high",
    suggestion:
      "Consider: 'Our coffee is crafted with wellness in mind' and add a supporting citation.",
    status: "open",
    dismissal_reason: null,
  },
  {
    id: "f-002",
    draft_id: "d-001",
    version_id: "v-001",
    quoted_text: "Founded in 1982 in Portland",
    start: 120,
    end: 148,
    severity: "warning",
    reason:
      "Fact FACT-03 records the founding year as 1985, not 1982. Please verify the correct date.",
    source_ref: "FACT-03",
    source_version: 2,
    confidence: "medium",
    suggestion: "Update to 'Founded in 1985 in Portland' per company records.",
    status: "open",
    dismissal_reason: null,
  },
  {
    id: "f-003",
    draft_id: "d-001",
    version_id: "v-001",
    quoted_text: "java",
    start: 210,
    end: 214,
    severity: "note",
    reason:
      "Terminology note: 'java' is informal. The preferred brand term per the style guide is 'premium roast coffee'.",
    source_ref: "TERM-05",
    source_version: 1,
    confidence: "low",
    suggestion: "Replace with 'premium roast coffee' for brand consistency.",
    status: "open",
    dismissal_reason: null,
  },
];

