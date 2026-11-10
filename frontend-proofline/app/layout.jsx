import "./styles.css";

export const metadata = {
  title: "ProofLine — Check it before you publish it.",
  description: "An evidence-backed workspace for brand review and approval.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
