export default function Footer() {
  return (
    <footer className="bg-white border-t border-gray-300 py-6 px-4 mt-auto text-center text-xs text-gray-500">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
        <div>
          <span className="font-semibold text-gray-700">ProofLine</span> — Pre-Publication Brand Governance Platform
          <span className="block sm:inline sm:ml-2 italic text-gray-400">
            &ldquo;Every claim linked to its proof. No source, no flag.&rdquo;
          </span>
        </div>
        <div className="text-gray-400">
          Code-Titans Hackathon · Team tanisha.khanna2022
        </div>
      </div>
    </footer>
  );
}
