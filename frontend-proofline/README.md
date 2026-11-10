# ProofLine frontend

ProofLine is a local Next.js demo of the Writer and Manager workflows for pre-publication brand review.

## Run locally

Use Node.js 20.9 or newer.

```sh
npm ci
npm run dev
```

Open http://localhost:3000 and choose a role. The matching demo credentials are prefilled. Run `npm run build` for a production build and `npm start` to serve it locally.

## Walk through the demo

1. Sign in as **Content Writer** and open **Summer launch email**. Inspect Pricing Sheet v3, apply the ₹999 to ₹1,299 correction, and request review.
2. Sign out and choose **Manager**. Open the draft in **Review queue**, enter a demo legal reference, then approve. The **Claim Receipt** shows the exact draft version and evidence used.
3. In **Brand library**, update **Starter plan pricing** and its approved text. **Alerts** shows the affected drafts and published items. **Audit log** records the actions.

## Current scope

- The demo uses local browser storage for content and session storage for the active role. Role sign-in and legal sign-off are simulations. Server-side identity, authorization, and shared storage are integration work.
- The local review rules live in `lib/workflow.mjs`. They cover seeded pricing and expiry, promotional phrases, terminology, basic tone patterns, a required disclaimer, empty Markdown alt text, and a contrast check for entered colors. Intent Lock records the writer's constraints for review. Grounded AI, semantic intent validation, automatic visual inspection, and live-channel integrations are backend work.
- PDF and DOCX imports extract editable text in the browser. Scanned PDFs require text pasted into the editor. The PDF.js browser bundle in `public/pdf` is version 5.6.205, distributed with its Apache 2.0 license.
- The normal-sized text contrast check follows [WCAG minimum contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
