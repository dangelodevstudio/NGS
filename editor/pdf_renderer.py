"""ReportLab-based PDF renderer for template B pages."""
from io import BytesIO
import re
import unicodedata

from django.contrib.staticfiles import finders
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import portrait
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph, Table, TableStyle

from .pdf_layout import get_layout


PURPLE = Color(117 / 255, 59 / 255, 189 / 255)
GRAY_TEXT = Color(89 / 255, 89 / 255, 89 / 255)


def _register_fonts():
    regular_path = finders.find("editor/fonts/RedHatDisplay-Regular.ttf")
    bold_path = finders.find("editor/fonts/RedHatDisplay-SemiBold.ttf")
    if regular_path:
        pdfmetrics.registerFont(TTFont("RedHatDisplay", regular_path))
    if bold_path:
        pdfmetrics.registerFont(TTFont("RedHatDisplayBold", bold_path))


def _draw_background(c, page_index, layout):
    bg_path = finders.find(f"editor/img/templates/laudo144_pg0{page_index}.png")
    if not bg_path:
        return
    img = ImageReader(bg_path)
    c.drawImage(img, 0, 0, width=layout.page_width * mm, height=layout.page_height * mm)


def _format_text(text):
    if not text:
        return ""
    return str(text).replace("\n", "<br/>")


def _style_for_field(layout, spec):
    color = PURPLE if spec.color == "purple" else GRAY_TEXT
    font_name = layout.font_bold if spec.font_name == "bold" else layout.font_regular
    return ParagraphStyle(
        name="field",
        fontName=font_name,
        boldFontName=layout.font_bold,
        fontSize=spec.font_size,
        leading=spec.leading,
        textColor=color,
        alignment=spec.align,
        wordWrap="LTR",
        splitLongWords=0,
    )


def _flow_in_frame(c, frame, flowables):
    story = list(flowables)
    frame._reset()
    while story:
        flowable = story[0]
        available_width = frame._getAvailableWidth()
        available_height = frame._y - frame._y1p
        if available_height <= 0:
            break
        _, flow_height = flowable.wrap(available_width, available_height)
        if flow_height <= available_height:
            frame.add(flowable, c)
            story.pop(0)
            continue
        parts = flowable.split(available_width, available_height)
        if not parts:
            break
        frame.add(parts[0], c)
        story = parts[1:] + story[1:]
    return story


def _draw_paragraph(c, layout, key, text):
    spec = layout.fields[key]
    style = _style_for_field(layout, spec)
    frame = Frame(
        spec.x * mm,
        (layout.page_height - spec.y - spec.h) * mm,
        spec.w * mm,
        spec.h * mm,
        leftPadding=spec.padding_x * mm,
        rightPadding=spec.padding_x * mm,
        topPadding=spec.padding_y * mm,
        bottomPadding=spec.padding_y * mm,
        showBoundary=0,
    )
    paragraph = Paragraph(_format_text(text), style)
    return _flow_in_frame(c, frame, [paragraph])


def _truncate_to_width(text, font_name, font_size, max_width):
    content = str(text or "")
    if pdfmetrics.stringWidth(content, font_name, font_size) <= max_width:
        return content
    ellipsis = "..."
    if pdfmetrics.stringWidth(ellipsis, font_name, font_size) > max_width:
        return ""
    while content and pdfmetrics.stringWidth(f"{content}{ellipsis}", font_name, font_size) > max_width:
        content = content[:-1]
    return f"{content}{ellipsis}"


def _draw_single_line_fitted(c, layout, key, text, min_font_size=8.0):
    spec = layout.fields[key]
    style = _style_for_field(layout, spec)
    font_name = style.fontName
    font_size = float(spec.font_size)
    min_size = float(min_font_size)
    available_width = max((spec.w - (spec.padding_x * 2)) * mm, 1)
    available_height = max((spec.h - (spec.padding_y * 2)) * mm, 1)
    rendered_text = str(text or "")

    while font_size > min_size and pdfmetrics.stringWidth(rendered_text, font_name, font_size) > available_width:
        font_size = round(font_size - 0.2, 2)

    rendered_text = _truncate_to_width(rendered_text, font_name, font_size, available_width)
    c.saveState()
    c.setFillColor(style.textColor)
    c.setFont(font_name, font_size)
    x_start = (spec.x + spec.padding_x) * mm
    if spec.align == 1:
        center_x = x_start + (available_width / 2.0)
    elif spec.align == 2:
        right_x = x_start + available_width
    y_bottom = (layout.page_height - spec.y - spec.h + spec.padding_y) * mm
    # Approximate baseline for vertical centering in a single-line label box.
    baseline = y_bottom + ((available_height - font_size) / 2.0) + (font_size * 0.25)
    if spec.align == 1:
        c.drawCentredString(center_x, baseline, rendered_text)
    elif spec.align == 2:
        c.drawRightString(right_x, baseline, rendered_text)
    else:
        c.drawString(x_start, baseline, rendered_text)
    c.restoreState()


def _paragraph_fits(layout, key, text):
    spec = layout.fields[key]
    style = _style_for_field(layout, spec)
    available_width = max((spec.w - (spec.padding_x * 2)) * mm, 1)
    available_height = max((spec.h - (spec.padding_y * 2)) * mm, 1)
    paragraph = Paragraph(_format_text(text), style)
    _, needed_height = paragraph.wrap(available_width, available_height)
    return needed_height <= available_height


def _split_single_paragraph_to_fit(layout, key, text):
    content = (text or "").strip()
    if not content:
        return "", ""
    if _paragraph_fits(layout, key, content):
        return content, ""

    breakpoints = [match.end() for match in re.finditer(r"\s+", content)]
    if not breakpoints or breakpoints[-1] != len(content):
        breakpoints.append(len(content))

    low = 0
    high = len(breakpoints) - 1
    best = 0
    while low <= high:
        middle = (low + high) // 2
        idx = breakpoints[middle]
        candidate = content[:idx].rstrip()
        if candidate and _paragraph_fits(layout, key, candidate):
            best = idx
            low = middle + 1
        else:
            high = middle - 1

    if best <= 0:
        return "", content
    return content[:best].rstrip(), content[best:].lstrip()


def _split_text_to_fit(layout, key, text):
    content = (text or "").strip()
    if not content:
        return "", ""
    if _paragraph_fits(layout, key, content):
        return content, ""

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    if not paragraphs:
        return "", ""

    accepted = []
    for index, paragraph in enumerate(paragraphs):
        candidate = "\n\n".join(accepted + [paragraph]).strip()
        if candidate and _paragraph_fits(layout, key, candidate):
            accepted.append(paragraph)
            continue

        if not accepted:
            head, tail = _split_single_paragraph_to_fit(layout, key, paragraph)
            rest = [part for part in [tail] + paragraphs[index + 1 :] if part]
            return head, "\n\n".join(rest).strip()

        remaining = "\n\n".join(paragraphs[index:]).strip()
        return "\n\n".join(accepted).strip(), remaining

    return "\n\n".join(accepted).strip(), ""


def _sanitize_methodology_text(text):
    if not text:
        return ""
    cleaned = unicodedata.normalize("NFKC", str(text))
    # Remove any bullet-like glyphs accidentally pasted into the content.
    cleaned = re.sub(r"[•●▪◦·]", " ", cleaned)
    # Some comparison glyphs render as black dots with the current PDF stack.
    cleaned = re.sub(r"≥\s*90%", "maior ou igual a 90%", cleaned)
    cleaned = re.sub(r">=\s*90%", "maior ou igual a 90%", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned


def _table_style(layout):
    return TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, -1), layout.font_regular),
            ("FONTSIZE", (0, 0), (-1, -1), 8.8),
            ("TEXTCOLOR", (0, 0), (-1, -1), GRAY_TEXT),
            ("LEFTPADDING", (0, 0), (-1, -1), 0.4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0.4),
            ("TOPPADDING", (0, 0), (-1, -1), 0.3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0.3),
        ]
    )


def _build_results_table(context, layout):
    cell_style = ParagraphStyle(
        "cell",
        fontName=layout.font_regular,
        boldFontName=layout.font_bold,
        fontSize=8.3,
        leading=9.0,
        textColor=GRAY_TEXT,
        alignment=1,
        wordWrap="LTR",
        splitLongWords=0,
    )
    data = [
        ["", "", "", "", "", ""],
        [
            "",
            Paragraph(
                f"{context.get('main_variant_c','')}<br/><nobr>{context.get('main_variant_p','')}</nobr>",
                cell_style,
            ),
            Paragraph(context.get("main_dbsnp", ""), cell_style),
            Paragraph(context.get("main_zygosity", ""), cell_style),
            Paragraph(context.get("main_inheritance", ""), cell_style),
            Paragraph(context.get("main_classification", ""), cell_style),
        ]
    ]
    spec = layout.tables["results"]
    table = Table(
        data,
        colWidths=[w * mm for w in spec.col_widths],
        rowHeights=[4.7 * mm, (spec.row_height - 4.7) * mm],
    )
    table.setStyle(_table_style(layout))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 1), (0, 1), PURPLE),
                ("VALIGN", (0, 1), (0, 1), "MIDDLE"),
                ("ALIGN", (0, 1), (0, 1), "CENTER"),
                ("TOPPADDING", (0, 1), (-1, 1), 0.0),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 0.2),
                ("LEFTPADDING", (0, 1), (-1, 1), 0.3),
                ("RIGHTPADDING", (0, 1), (-1, 1), 0.3),
            ]
        )
    )
    return table


def _build_vus_table(context, layout):
    gene_style = ParagraphStyle(
        "vus_gene",
        fontName=layout.font_regular,
        boldFontName=layout.font_bold,
        fontSize=8.2,
        leading=8.8,
        textColor=GRAY_TEXT,
        alignment=1,
        wordWrap="LTR",
        splitLongWords=0,
    )
    cell_style = ParagraphStyle(
        "vus_cell",
        fontName=layout.font_regular,
        boldFontName=layout.font_bold,
        fontSize=8.2,
        leading=8.8,
        textColor=GRAY_TEXT,
        alignment=1,
        wordWrap="LTR",
        splitLongWords=0,
    )
    data = [
        [
            Paragraph(
                f"<b>{context.get('vus_gene','')}</b><br/><nobr>{context.get('vus_transcript','')}</nobr>",
                gene_style,
            ),
            Paragraph(
                f"{context.get('vus_variant_c','')} <nobr>{context.get('vus_variant_p','')}</nobr>",
                cell_style,
            ),
            Paragraph(context.get("vus_dbsnp", ""), cell_style),
            Paragraph(context.get("vus_zygosity", ""), cell_style),
            Paragraph(context.get("vus_inheritance", ""), cell_style),
            Paragraph(context.get("vus_classification", ""), cell_style),
        ]
    ]
    spec = layout.tables["vus"]
    table = Table(
        data,
        colWidths=[w * mm for w in spec.col_widths],
        rowHeights=[spec.row_height * mm],
    )
    table.setStyle(_table_style(layout))
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0.2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0.2),
                ("TOPPADDING", (0, 0), (-1, -1), 0.0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
            ]
        )
    )
    return table


def _draw_header(c, layout, context):
    _draw_single_line_fitted(c, layout, "header.name", f"Nome: {context.get('patient_name','')}")
    _draw_paragraph(c, layout, "header.birth", f"<b>Data de Nascimento:</b> {context.get('patient_birth_date','')}")
    _draw_paragraph(c, layout, "header.sex", f"<b>Sexo:</b> {context.get('patient_sex','')}")
    _draw_paragraph(c, layout, "header.code", f"<b>Código ID:</b> {context.get('patient_code','')}")
    _draw_paragraph(c, layout, "header.entry", f"<b>Data de Entrada:</b> {context.get('exam_entry_date','')}")
    _draw_paragraph(c, layout, "header.release", f"<b>Data de Liberação:</b> {context.get('exam_release_date','')}")


def draw_footer(c, layout, context):
    _draw_paragraph(
        c,
        layout,
        "footer.analyst",
        f"Analista responsável: {context.get('analyst_name','')} {context.get('analyst_registry','')}",
    )
    _draw_paragraph(
        c,
        layout,
        "footer.tech",
        f"Profissional técnico: {context.get('lab_tech_name','')} {context.get('lab_tech_registry','')}",
    )
    _draw_paragraph(
        c,
        layout,
        "footer.md",
        f"Médico Responsável: {context.get('geneticist_name','')} {context.get('geneticist_registry','')}",
    )
    _draw_paragraph(
        c,
        layout,
        "footer.director",
        f"Responsável técnico: {context.get('director_name','')} {context.get('director_registry','')}",
    )


def _draw_table(c, layout, spec_key, table):
    spec = layout.tables[spec_key]
    table_x = spec.x * mm
    table_y = (layout.page_height - spec.y - spec.row_height) * mm
    table.wrapOn(c, 0, 0)
    table.drawOn(c, table_x, table_y)


def _draw_results_gene_centered(c, layout, context):
    spec = layout.tables["results"]
    header_h_mm = 4.7
    data_h_mm = spec.row_height - header_h_mm
    x = spec.x * mm
    y = (layout.page_height - spec.y - spec.row_height) * mm
    w = spec.col_widths[0] * mm
    cx = x + (w / 2.0)
    cy = y + ((data_h_mm * mm) / 2.0)

    gene = (context.get("main_gene", "") or "").strip()
    transcript = (context.get("main_transcript", "") or "").strip()
    if not gene and not transcript:
        return

    c.saveState()
    c.setFillColor(Color(1, 1, 1))
    # Keep both lines centered as a block inside the purple data cell.
    c.setFont(layout.font_bold, 10.8)
    c.drawCentredString(cx, cy - 2.4, gene)
    c.setFont(layout.font_regular, 9.0)
    c.drawCentredString(cx, cy - 11.4, transcript)
    c.restoreState()


def render_template_b_pdf(context):
    _register_fonts()
    layout = get_layout()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=portrait((layout.page_width * mm, layout.page_height * mm)))

    # Page 1 (cover)
    _draw_background(c, 1, layout)
    _draw_paragraph(c, layout, "p1.name", f"<b>Nome:</b> {context.get('patient_name','')}")
    _draw_paragraph(c, layout, "p1.birth", f"<b>Data de Nascimento:</b> {context.get('patient_birth_date_cover','')}")
    _draw_paragraph(c, layout, "p1.code", f"<b>Código ID:</b> {context.get('patient_code_cover','')}")
    c.showPage()

    # Page 2
    _draw_background(c, 2, layout)
    _draw_header(c, layout, context)
    requester_line = f"<b>Solicitante:</b>&nbsp;{context.get('requester_display') or context.get('requester_name','')}"
    sample_line = f"<b>Amostra:</b>&nbsp;{context.get('sample_display') or context.get('sample_description','')}"
    clinical_indication = (context.get("clinical_indication") or "").strip()
    data_lines = [requester_line, sample_line]
    if clinical_indication:
        data_lines.append(f"<b>Indicação clínica:</b>&nbsp;{clinical_indication}")
    data_lines.append("")
    data_lines.append(f"Nome do exame: <b>{context.get('exam_name','')}</b>")
    _draw_paragraph(c, layout, "p2.data", "\n".join(data_lines))
    result_intro = (
        context.get("main_result_intro")
        or "Foi identificada uma variante clinicamente relevante no gene TP53."
    )
    _draw_paragraph(c, layout, "p2.results", result_intro)
    _draw_paragraph(c, layout, "p2.condition", f"Condição: {context.get('main_condition','')}")
    inheritance_legend = (context.get("main_inheritance_legend") or "").strip()
    if inheritance_legend:
        _draw_paragraph(c, layout, "p2.inheritance_legend", inheritance_legend)
    interpretation_source = context.get("interpretation_text", "")
    interpretation_p2, interpretation_remaining = _split_text_to_fit(
        layout,
        "p2.interpretation",
        interpretation_source,
    )
    if interpretation_p2:
        _draw_paragraph(c, layout, "p2.interpretation", interpretation_p2)
    _draw_table(c, layout, "results", _build_results_table(context, layout))
    _draw_results_gene_centered(c, layout, context)
    draw_footer(c, layout, context)
    c.showPage()

    # Page 3
    _draw_background(c, 3, layout)
    _draw_header(c, layout, context)
    interpretation_p3, interpretation_overflow = _split_text_to_fit(
        layout,
        "p3.interpretation",
        interpretation_remaining,
    )
    if interpretation_p3:
        _draw_paragraph(c, layout, "p3.interpretation", interpretation_p3)

    additional_text = context.get("additional_findings_text", "")
    if interpretation_overflow:
        additional_text = f"{interpretation_overflow}\n\n{additional_text}".strip()
    additional_text = additional_text.strip()
    _draw_paragraph(c, layout, "p3.additional", additional_text)
    _draw_table(c, layout, "vus", _build_vus_table(context, layout))
    draw_footer(c, layout, context)
    c.showPage()

    # Page 4
    _draw_background(c, 4, layout)
    _draw_header(c, layout, context)
    _draw_paragraph(c, layout, "p4.genes", context.get("genes_analyzed_p4") or context.get("genes_analyzed_list", ""))
    draw_footer(c, layout, context)
    c.showPage()

    # Page 5
    _draw_background(c, 5, layout)
    _draw_header(c, layout, context)
    metrics_base = (context.get("metrics_coverage_base") or "50x").strip() or "50x"
    _draw_paragraph(c, layout, "p5.metrics.title", "DNA Nuclear")
    _draw_paragraph(c, layout, "p5.metrics.label_mean", "Cobertura média da região alvo:")
    _draw_paragraph(c, layout, "p5.metrics.label_50x", f"% da região alvo com cobertura maior ou igual a {metrics_base}:")
    _draw_paragraph(c, layout, "p5.metrics.note", "Região alvo refere-se a região codificante e sítios de splicing dos genes analisados.")
    _draw_single_line_fitted(c, layout, "p5.metrics.mean", context.get("metrics_coverage_mean", ""), min_font_size=8.2)
    _draw_single_line_fitted(c, layout, "p5.metrics.50x", context.get("metrics_coverage_50x", ""), min_font_size=8.2)
    if context.get("is_admin"):
        _draw_paragraph(c, layout, "p5.recommendations", context.get("recommendations_text", ""))
    notes_text = re.sub(r"\s*\n+\s*", " ", (context.get("notes_text", "") or "").strip())
    notes_text = re.sub(r"\s{2,}", " ", notes_text)
    _draw_paragraph(c, layout, "p5.notes", notes_text)
    draw_footer(c, layout, context)
    c.showPage()

    # Page 6
    _draw_background(c, 6, layout)
    _draw_header(c, layout, context)
    # Page 6 background already contains "CONSIDERAÇÕES E LIMITAÇÕES" and
    # "OBSERVAÇÕES" blocks in this template family; only methodology text is
    # overlaid here to avoid duplicated content.
    _draw_paragraph(c, layout, "p6.methodology", _sanitize_methodology_text(context.get("methodology_text", "")))
    draw_footer(c, layout, context)
    c.showPage()

    # Page 7
    _draw_background(c, 7, layout)
    _draw_header(c, layout, context)
    # Page 7 background includes the references section for this template.
    draw_footer(c, layout, context)
    c.showPage()

    # Page 8 (institutional back cover)
    _draw_background(c, 8, layout)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
