---
name: pdf-to-md
description: Turns PDFs into Markdown with Docling, keeping headings, tables, pictures and page numbers, so the other skills can read and cite them. Use for the brief, development plans, studies, reports, statistics, references, or any PDF relevant to the project, when asked to convert a PDF to Markdown, or when a skill needs a PDF as text.
---

# PDF to Markdown

Reads: nothing, only the PDFs in the project

Much of what a project needs comes as PDF: the brief, a development plan, a traffic or noise study, city statistics, a reference project. The other skills read text. This skill converts each PDF with Docling, which keeps headings, lists and tables in reading order, so a number in a table stays next to its label. A marker `<!-- page N -->` stands before each page, so whoever takes a number from it can cite the file and the page.

Convert the PDFs the user names, or else every PDF in the project that has no Markdown yet. Write each result next to its PDF, so every version of a proposal reads the same text. For each: `python "${CLAUDE_SKILL_DIR}/scripts/pdf_to_md.py" <pdf> <the PDF's folder>/ --images`. Add `--ocr` only if a page comes out empty but has text in the PDF, a scan. It writes `<name>.md` and the pictures (maps, plans, drawings, photos) at 300 dpi to `<name>-images/`, named by page, leaving out icons and logos under 3 cm. Plans and maps drawn in vectors also go to `<name>-drawings/` with the legend beside them, as PDF, SVG and PNG (`pip install pymupdf`). The first run downloads Docling's models, about 500 MB. If Docling isn't installed: `pip install docling`.

Then read each result against its PDF on a few pages with tables or key numbers. Fix nothing by hand. Next to each, write `<name>-summary.md`, one page at most, from its Markdown: what the document is and from whom, then what matters most in it (the task, key numbers and areas, dates, what it requires), each line with its page `(p. N)`. Only what it says; add nothing. Keep an `index.md` in the same folder, one line per PDF: where it came from, what it is, its pages. Write `summary.md` next to it, in three lines: which PDFs were converted, how many pages and tables, and any page that came out wrong or empty.
