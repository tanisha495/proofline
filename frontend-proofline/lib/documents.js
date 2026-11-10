import { unzipSync, strFromU8 } from "fflate";

export async function extractDocument(file) {
  if (file.size > 15 * 1024 * 1024)
    throw new Error("Choose a document smaller than 15 MB.");
  const name = file.name.toLowerCase();
  if (!name.endsWith(".pdf") && !name.endsWith(".docx"))
    throw new Error("Choose a PDF or DOCX file.");
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (name.endsWith(".docx")) {
    const archive = unzipSync(bytes, {
      filter: (file) =>
        file.name === "word/document.xml" &&
        file.originalSize < 20 * 1024 * 1024,
    });
    if (!archive["word/document.xml"])
      throw new Error("This Word document could not be read.");
    const xml = new DOMParser().parseFromString(
      strFromU8(archive["word/document.xml"]),
      "application/xml"
    );
    const ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
    return Array.from(xml.getElementsByTagNameNS(ns, "p"), (p) =>
      Array.from(
        p.getElementsByTagNameNS(ns, "t"),
        (node) => node.textContent
      ).join("")
    )
      .join("\n")
      .trim();
  }

  // Load the browser distribution only when a writer imports a PDF.
  const pdfjs = await import(/* webpackIgnore: true */ "/pdf/pdf.min.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf/pdf.worker.min.mjs";
  const task = pdfjs.getDocument({ data: bytes, isEvalSupported: false });
  try {
    const pdf = await task.promise;
    const pages = [];
    for (let number = 1; number <= pdf.numPages; number++) {
      const page = await pdf.getPage(number);
      const { items } = await page.getTextContent();
      pages.push(
        items
          .map((item) =>
            item.str ? item.str + (item.hasEOL ? "\n" : " ") : ""
          )
          .join("")
          .trim()
      );
    }
    return pages.join("\n\n").trim();
  } finally {
    await task.destroy();
  }
}
