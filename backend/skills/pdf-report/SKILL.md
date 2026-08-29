---
name: PDF Report Generator
description: Produce a polished, well-formatted PDF report (title page, sections, tables, charts) from data or research findings.
triggers: [pdf, report, invoice, one-pager, summary document]
---

# PDF Report Generator

When the user wants a PDF deliverable (a report, invoice, summary, or one-pager):

1. Use `run_bash` to ensure `reportlab` is available: `pip show reportlab || pip install --user reportlab`.
2. Use `write_file` to create a Python script (e.g. `make_report.py`) that:
   - Uses `reportlab.platypus` (`SimpleDocTemplate`, `Paragraph`, `Table`, `Spacer`, `PageBreak`) for layout.
   - Defines a clean style sheet: a bold title, section headings (`Heading2`), body text (`BodyText`).
   - Builds tables with `Table(...)` + `TableStyle` for any tabular data, alternating row shading for readability.
   - Writes the output to `report.pdf` in the current workspace directory.
3. Run the script with `run_python` or `run_bash` (`python make_report.py`) and confirm it exits 0.
4. Use `make_document` or point the user at the download link so they can retrieve `report.pdf`.
5. Keep the report skimmable: an executive summary paragraph up top, clear section headers, and a table
   or bullet list wherever you'd otherwise write a wall of prose.

Never fabricate data — if the user hasn't given you numbers, ask a clarifying question or clearly label
placeholder figures as illustrative.
