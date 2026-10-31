#!/usr/bin/env python3
"""
Convert one PDF to Markdown with Docling, page by page, with a page marker
before each page so numbers taken from it can cite their page.

Usage:
    python pdf_to_md.py <input_pdf> <output_dir> [--images] [--ocr]

Writes <output_dir>/<pdf name>.md and, with --images, the pictures at 300 dpi,
leaving out those under 3 cm (icons, logos), to
<output_dir>/<pdf name>-images/p<page>-<n>.png, and the pictures drawn in
vectors (plans, maps) with their legend, as PDF, SVG and PNG, to
<output_dir>/<pdf name>-drawings/ (needs PyMuPDF).
"""

import os
import sys
import warnings
from pathlib import Path

os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
warnings.filterwarnings('ignore')

DPI = 300  # resolution of the saved pictures
MIN_CM = 3  # smaller pictures on the page are left out
MIN_PATHS = 500  # a picture with this many vector lines is a drawing


def convert(input_pdf, output_dir, images=False, ocr=False):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
    pipeline_options.do_ocr = ocr
    pipeline_options.generate_picture_images = images
    pipeline_options.images_scale = DPI / 72

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )

    input_pdf = Path(input_pdf)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Converting {input_pdf.name}...")
    doc = converter.convert(str(input_pdf)).document

    # One page at a time, so empty pages still get their marker
    parts = [f"# {input_pdf.stem}\n\n*Converted with Docling from `{input_pdf.name}`.*"]
    for page_no in sorted(doc.pages):
        parts.append(f"<!-- page {page_no} -->\n\n{doc.export_to_markdown(page_no=page_no)}")
    output_md = output_dir / f"{input_pdf.stem}.md"
    output_md.write_text("\n\n".join(parts) + "\n", encoding='utf-8')

    if images:
        image_dir = output_dir / f"{input_pdf.stem}-images"
        image_dir.mkdir(exist_ok=True)
        count = {}
        for element, _level in doc.iterate_items():
            image = getattr(element, 'image', None)
            if image is None or not element.prov:
                continue
            # Skip icons, logos and legend symbols: shorter side under MIN_CM on the page
            bbox = element.prov[0].bbox
            if min(abs(bbox.r - bbox.l), abs(bbox.t - bbox.b)) < MIN_CM / 2.54 * 72:
                continue
            page_no = element.prov[0].page_no
            count[page_no] = count.get(page_no, 0) + 1
            image.pil_image.save(str(image_dir / f"p{page_no}-{count[page_no]}.png"))
        save_drawings(input_pdf, doc, output_dir)

    print(f"Output: {output_md} ({len(doc.pages)} pages)")
    return output_md


def save_drawings(input_pdf, doc, output_dir):
    """Cut each picture drawn in vectors (a plan, a map) with the legend beside it, as PDF, SVG and PNG."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("Drawings skipped: pip install pymupdf")
        return
    pdf = fitz.open(str(input_pdf))
    out = output_dir / f"{input_pdf.stem}-drawings"
    lines, count, cuts = {}, {}, {}
    for element, _level in doc.iterate_items():
        if str(element.label) != 'picture' or not element.prov:
            continue
        page_no = element.prov[0].page_no
        page = pdf[page_no - 1]
        if page_no not in lines:
            lines[page_no] = [d['rect'] for d in page.get_drawings()]
        b = element.prov[0].bbox.to_top_left_origin(page.rect.height)
        pic = fitz.Rect(b.l, b.t, b.r, b.b)
        if sum(pic.contains(r) for r in lines[page_no]) < MIN_PATHS:
            continue  # a photo or a raster image, not a drawing
        if any(pic.intersects(c) for c in cuts.setdefault(page_no, [])):
            continue  # part of a drawing already cut
        # Take in the legend: text and symbols beside the drawing, within its height
        clip = fitz.Rect(pic)
        beside = [fitz.Rect(t[:4]) for t in page.get_text('blocks')] + lines[page_no]
        for r in beside:
            if (r.y0 >= pic.y0 - 5 and r.y1 <= pic.y1 + 5 and not r.is_empty
                    and (r.x0 >= pic.x1 - 1 or r.x1 <= pic.x0 + 1)):
                clip |= r
        clip = (clip + (-3, -3, 3, 3)) & page.rect
        cuts[page_no].append(clip)
        count[page_no] = count.get(page_no, 0) + 1
        name = out / f"p{page_no}-{count[page_no]}"
        out.mkdir(exist_ok=True)
        cut = fitz.open()
        cut.new_page(width=clip.width, height=clip.height).show_pdf_page(
            fitz.Rect(0, 0, clip.width, clip.height), pdf, page_no - 1, clip=clip)
        cut.save(f"{name}.pdf", garbage=4, deflate=True)
        Path(f"{name}.svg").write_text(cut[0].get_svg_image(), encoding='utf-8')
        page.get_pixmap(dpi=DPI, clip=clip).save(f"{name}.png")
    if count:
        print(f"Drawings: {sum(count.values())} in {out}")


def main():
    args = sys.argv[1:]
    flags = {a for a in args if a.startswith('--')}
    paths = [a for a in args if not a.startswith('--')]
    if len(paths) != 2 or flags - {'--images', '--ocr'}:
        print(__doc__)
        sys.exit(1)

    if not Path(paths[0]).exists():
        print(f"Error: {paths[0]} not found")
        sys.exit(1)

    try:
        convert(paths[0], paths[1], images='--images' in flags, ocr='--ocr' in flags)
    except ImportError as e:
        print("Error: Missing dependency. Run: pip install docling")
        print(f"Details: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
