"""ReportLab-based PDF renderer for template B pages."""
from io import BytesIO

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
        wordWrap="CJK",
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
    paragraph = Paragraph(_format_text(text), _style_for_field(layout, spec))
    return _flow_in_frame(c, frame, [paragraph])


def _table_style(layout):
    return TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, -1), layout.font_regular),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (-1, -1), GRAY_TEXT),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]
    )


def _build_results_table(context, layout):
    gene_style = ParagraphStyle(
        "gene",
        fontName=layout.font_regular,
        boldFontName=layout.font_bold,
        fontSize=10,
        leading=12,
        textColor=Color(1, 1, 1),
        alignment=1,
        wordWrap="LTR",
        splitLongWords=0,
    )
    cell_style = ParagraphStyle(
        "cell",
        fontName=layout.font_regular,
        boldFontName=layout.font_bold,
        fontSize=10,
        leading=12,
        textColor=GRAY_TEXT,
        alignment=1,
        wordWrap="LTR",
        splitLongWords=0,
    )
    data = [
        [
            Paragraph(f"<b>{context.get('main_gene','')}</b><br/>{context.get('main_transcript','')}", gene_style),
            Paragraph(
                f"{context.get('main_variant_c','')}<br/>{context.get('main_variant_p','')}",
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
        rowHeights=[spec.row_height * mm],
    )
    table.setStyle(_table_style(layout))
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), PURPLE)]))
    return table


def _build_vus_table(context, layout):
    gene_style = ParagraphStyle(
        "vus_gene",
        fontName=layout.font_regular,
        boldFontName=layout.font_bold,
        fontSize=10,
        leading=12,
        textColor=Color(1, 1, 1),
        alignment=1,
        wordWrap="LTR",
        splitLongWords=0,
    )
    cell_style = ParagraphStyle(
        "vus_cell",
        fontName=layout.font_regular,
        boldFontName=layout.font_bold,
        fontSize=10,
        leading=12,
        textColor=GRAY_TEXT,
        alignment=1,
        wordWrap="LTR",
        splitLongWords=0,
    )
    data = [
        [
            Paragraph(f"<b>{context.get('vus_gene','')}</b><br/>{context.get('vus_transcript','')}", gene_style),
            Paragraph(f"{context.get('vus_variant_c','')} {context.get('vus_variant_p','')}", cell_style),
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
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), PURPLE)]))
    return table


def _draw_header(c, layout, context):
    _draw_paragraph(c, layout, "header.name", f"<b>Nome:</b> {context.get('patient_name','')}")
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
    draw_footer(c, layout, context)
    c.showPage()

    # Page 2
    _draw_background(c, 2, layout)
    _draw_header(c, layout, context)
    _draw_paragraph(c, layout, "p2.requester", f"<b>Solicitante:</b> {context.get('requester_display') or context.get('requester_name','')}")
    _draw_paragraph(c, layout, "p2.sample", f"<b>Amostra:</b> {context.get('sample_display') or context.get('sample_description','')}")
    _draw_paragraph(c, layout, "p2.clinical", f"<b>Indicação clínica:</b> {context.get('clinical_indication','')}")
    _draw_paragraph(c, layout, "p2.exam", f"<b>Nome do exame:</b> {context.get('exam_name','')}")
    _draw_paragraph(c, layout, "p2.results", context.get("main_result_intro", ""))
    _draw_paragraph(c, layout, "p2.condition", f"Condição: {context.get('main_condition','')}")
    _draw_table(c, layout, "results", _build_results_table(context, layout))
    draw_footer(c, layout, context)

    # Interpretation (page 2)
    leftover = _draw_paragraph(
        c,
        layout,
        "p2.interpretation",
        context.get("interpretation_text", ""),
    )
    c.showPage()

    # Page 3
    _draw_background(c, 3, layout)
    _draw_header(c, layout, context)
    overflow = []
    if leftover:
        spec = layout.fields["p3.interpretation"]
        frame_leftover = Frame(
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
        overflow = _flow_in_frame(c, frame_leftover, leftover)
    _draw_paragraph(c, layout, "p3.additional", context.get("additional_findings_p3") or context.get("additional_findings_text", ""))
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
    _draw_paragraph(c, layout, "p5.notes_subtitle", "ACHADOS SECUNDÁRIOS")
    _draw_paragraph(c, layout, "p5.notes", context.get("notes_text", ""))
    if context.get("is_admin"):
        _draw_paragraph(c, layout, "p5.recommendations", context.get("recommendations_text", ""))
    _draw_paragraph(c, layout, "p5.metrics.title", "DNA Nuclear")
    _draw_paragraph(c, layout, "p5.metrics.label_mean", "Cobertura média da região alvo:")
    _draw_paragraph(c, layout, "p5.metrics.label_50x", "% da região alvo com cobertura maior ou igual a 50x:")
    _draw_paragraph(c, layout, "p5.metrics.note", "Região alvo refere-se a região codificante e sítios de splicing dos genes analisados.")
    _draw_paragraph(c, layout, "p5.metrics.mean", context.get("metrics_coverage_mean", ""))
    _draw_paragraph(c, layout, "p5.metrics.50x", context.get("metrics_coverage_50x", ""))
    draw_footer(c, layout, context)
    c.showPage()

    # Page 6
    _draw_background(c, 6, layout)
    _draw_header(c, layout, context)
    _draw_paragraph(c, layout, "p6.methodology", context.get("methodology_text", ""))
    draw_footer(c, layout, context)
    c.showPage()

    # Page 7
    _draw_background(c, 7, layout)
    _draw_header(c, layout, context)
    draw_footer(c, layout, context)
    c.showPage()

    # Overflow pages for interpretation (if any)
    used_overflow = False
    while overflow:
        used_overflow = True
        _draw_background(c, 8, layout)
        _draw_header(c, layout, context)
        draw_footer(c, layout, context)
        frame_overflow = Frame(
            12.70 * mm,
            (layout.page_height - 75.93 - 175.93) * mm,
            165.10 * mm,
            175.93 * mm,
            leftPadding=layout.padding_x * mm,
            rightPadding=layout.padding_x * mm,
            topPadding=layout.padding_y * mm,
            bottomPadding=layout.padding_y * mm,
            showBoundary=0,
        )
        overflow = _flow_in_frame(c, frame_overflow, overflow)
        if overflow:
            c.showPage()

    # Page 8 (background only) if no overflow
    if not used_overflow:
        _draw_background(c, 8, layout)
        _draw_header(c, layout, context)
        draw_footer(c, layout, context)

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
