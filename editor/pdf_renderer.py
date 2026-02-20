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
BG_PAGE = Color(245 / 255, 243 / 255, 247 / 255)
BG_PANEL = Color(235 / 255, 231 / 255, 242 / 255)
BORDER_PURPLE = Color(185 / 255, 154 / 255, 231 / 255)
TABLE_HEADER_BG = Color(239 / 255, 235 / 255, 247 / 255)


def _register_fonts():
    regular_path = finders.find("editor/fonts/RedHatDisplay-Regular.ttf")
    bold_path = finders.find("editor/fonts/RedHatDisplay-SemiBold.ttf")
    if regular_path:
        pdfmetrics.registerFont(TTFont("RedHatDisplay", regular_path))
    if bold_path:
        pdfmetrics.registerFont(TTFont("RedHatDisplayBold", bold_path))


def _y_from_top(layout, y_mm, h_mm):
    return (layout.page_height - y_mm - h_mm) * mm


def _draw_image(c, layout, rel_path, x_mm, y_mm, w_mm, h_mm, preserve=True):
    path = finders.find(rel_path)
    if not path:
        return
    img = ImageReader(path)
    c.drawImage(
        img,
        x_mm * mm,
        _y_from_top(layout, y_mm, h_mm),
        width=w_mm * mm,
        height=h_mm * mm,
        preserveAspectRatio=preserve,
        mask="auto",
        anchor="c",
    )


def _draw_round_rect(c, layout, x_mm, y_mm, w_mm, h_mm, radius_mm=2.8, stroke=1, fill=0, stroke_color=BORDER_PURPLE, fill_color=None):
    c.saveState()
    c.setStrokeColor(stroke_color)
    if fill_color:
        c.setFillColor(fill_color)
    c.roundRect(
        x_mm * mm,
        _y_from_top(layout, y_mm, h_mm),
        w_mm * mm,
        h_mm * mm,
        radius_mm * mm,
        stroke=stroke,
        fill=fill,
    )
    c.restoreState()


def _draw_section_box(c, layout, x_mm, y_mm, w_mm, h_mm, title):
    _draw_round_rect(c, layout, x_mm, y_mm, w_mm, h_mm, radius_mm=2.2, stroke=1, fill=0)
    pill_w = max(44.0, min(62.0, 12.0 + len(str(title or "")) * 2.0))
    pill_h = 8.0
    pill_x = x_mm - 0.4
    pill_y = y_mm - (pill_h / 2.0)
    _draw_round_rect(
        c,
        layout,
        pill_x,
        pill_y,
        pill_w,
        pill_h,
        radius_mm=4.0,
        stroke=0,
        fill=1,
        fill_color=PURPLE,
    )
    c.saveState()
    c.setFillColor(Color(1, 1, 1))
    c.setFont(layout.font_bold, 9.2)
    text_y = _y_from_top(layout, pill_y, pill_h) + (pill_h * mm * 0.35)
    c.drawCentredString((pill_x + (pill_w / 2.0)) * mm, text_y, str(title or "").upper())
    c.restoreState()


def _draw_page_shell(c, layout, page_index):
    if page_index == 1:
        front_cover = finders.find("capa.png")
        if front_cover:
            c.drawImage(
                ImageReader(front_cover),
                0,
                0,
                width=layout.page_width * mm,
                height=layout.page_height * mm,
                preserveAspectRatio=False,
                mask="auto",
            )
            return
        c.setFillColor(BG_PAGE)
        c.rect(0, 0, layout.page_width * mm, layout.page_height * mm, stroke=0, fill=1)
        bg = finders.find("editor/img/elements/bg_network.png")
        if bg:
            c.drawImage(
                ImageReader(bg),
                0,
                0,
                width=layout.page_width * mm,
                height=layout.page_height * mm,
                preserveAspectRatio=False,
                mask="auto",
            )
        return

    if page_index == 8:
        back_cover = finders.find("capa-rodape.png")
        if back_cover:
            c.drawImage(
                ImageReader(back_cover),
                0,
                0,
                width=layout.page_width * mm,
                height=layout.page_height * mm,
                preserveAspectRatio=False,
                mask="auto",
            )
            return
        c.setFillColor(BG_PAGE)
        c.rect(0, 0, layout.page_width * mm, layout.page_height * mm, stroke=0, fill=1)
        bg = finders.find("editor/img/elements/bg_network.png")
        if bg:
            c.drawImage(
                ImageReader(bg),
                0,
                0,
                width=layout.page_width * mm,
                height=layout.page_height * mm,
                preserveAspectRatio=False,
                mask="auto",
            )
        return

    c.setFillColor(BG_PAGE)
    c.rect(0, 0, layout.page_width * mm, layout.page_height * mm, stroke=0, fill=1)

    # Cabeçalho fixo (6 páginas internas: 2..7).
    _draw_image(
        c,
        layout,
        "cabecalho.png",
        x_mm=0.0,
        y_mm=0.0,
        w_mm=layout.page_width,
        h_mm=58.8,
        preserve=False,
    )
    # Remove o texto placeholder do asset e mantém caixa/borda do cabeçalho.
    _draw_round_rect(
        c,
        layout,
        x_mm=71.2,
        y_mm=11.0,
        w_mm=104.6,
        h_mm=33.8,
        radius_mm=2.4,
        stroke=0,
        fill=1,
        fill_color=Color(1, 1, 1),
    )

    # Rodapé fixo por imagem (texto/layout estático).
    footer_height = layout.page_width * (157.0 / 1078.0)
    footer_top = layout.page_height - footer_height
    _draw_image(
        c,
        layout,
        "footer.png",
        x_mm=0.0,
        y_mm=footer_top,
        w_mm=layout.page_width,
        h_mm=footer_height,
        preserve=False,
    )


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


def _draw_label_with_bold_value(c, layout, key, label, value, min_font_size=8.0):
    spec = layout.fields[key]
    style = _style_for_field(layout, spec)
    label_text = str(label or "")
    value_text = str(value or "")
    regular_font = layout.font_regular
    bold_font = layout.font_bold
    font_size = float(spec.font_size)
    min_size = float(min_font_size)
    available_width = max((spec.w - (spec.padding_x * 2)) * mm, 1)
    available_height = max((spec.h - (spec.padding_y * 2)) * mm, 1)

    total_width = (
        pdfmetrics.stringWidth(label_text, regular_font, font_size)
        + pdfmetrics.stringWidth(value_text, bold_font, font_size)
    )
    while font_size > min_size and total_width > available_width:
        font_size = round(font_size - 0.2, 2)
        total_width = (
            pdfmetrics.stringWidth(label_text, regular_font, font_size)
            + pdfmetrics.stringWidth(value_text, bold_font, font_size)
        )

    label_width = pdfmetrics.stringWidth(label_text, regular_font, font_size)
    remaining_width = max(available_width - label_width, 1)
    value_rendered = _truncate_to_width(value_text, bold_font, font_size, remaining_width)

    c.saveState()
    c.setFillColor(style.textColor)
    x_start = (spec.x + spec.padding_x) * mm
    y_bottom = (layout.page_height - spec.y - spec.h + spec.padding_y) * mm
    baseline = y_bottom + ((available_height - font_size) / 2.0) + (font_size * 0.25)

    c.setFont(regular_font, font_size)
    c.drawString(x_start, baseline, label_text)
    c.setFont(bold_font, font_size)
    c.drawString(x_start + label_width, baseline, value_rendered)
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
            ("FONTSIZE", (0, 0), (-1, -1), 8.6),
            ("TEXTCOLOR", (0, 0), (-1, -1), GRAY_TEXT),
            ("LEFTPADDING", (0, 0), (-1, -1), 0.6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0.6),
            ("TOPPADDING", (0, 0), (-1, -1), 0.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
            ("GRID", (0, 0), (-1, -1), 0.35, BORDER_PURPLE),
        ]
    )


def _clean_row_value(row, key):
    return str((row or {}).get(key, "") or "").strip()


def _get_main_variant_rows(context):
    rows = context.get("main_variant_rows")
    if isinstance(rows, list) and rows:
        return rows
    legacy = {
        "gene": context.get("main_gene", ""),
        "transcript": context.get("main_transcript", ""),
        "variant_c": context.get("main_variant_c", ""),
        "variant_p": context.get("main_variant_p", ""),
        "dbsnp": context.get("main_dbsnp", ""),
        "zygosity": context.get("main_zygosity", ""),
        "inheritance": context.get("main_inheritance", ""),
        "classification": context.get("main_classification", ""),
        "condition": context.get("main_condition", ""),
    }
    return [legacy] if any(str(v or "").strip() for v in legacy.values()) else []


def _get_additional_variant_rows(context):
    rows = context.get("additional_variant_rows")
    if isinstance(rows, list) and rows:
        return rows
    legacy = {
        "gene": context.get("vus_gene", ""),
        "transcript": context.get("vus_transcript", ""),
        "variant_c": context.get("vus_variant_c", ""),
        "variant_p": context.get("vus_variant_p", ""),
        "dbsnp": context.get("vus_dbsnp", ""),
        "zygosity": context.get("vus_zygosity", ""),
        "inheritance": context.get("vus_inheritance", ""),
        "classification": context.get("vus_classification", ""),
        "condition": "",
    }
    return [legacy] if any(str(v or "").strip() for v in legacy.values()) else []


def _get_cnv_rows(context, key):
    rows = context.get(key)
    if isinstance(rows, list):
        return rows
    return []


def _format_variant_rows_for_overflow(rows):
    lines = []
    for index, row in enumerate(rows or [], start=1):
        gene = _clean_row_value(row, "gene")
        transcript = _clean_row_value(row, "transcript")
        var_c = _clean_row_value(row, "variant_c")
        var_p = _clean_row_value(row, "variant_p")
        dbsnp = _clean_row_value(row, "dbsnp")
        zyg = _clean_row_value(row, "zygosity")
        inh = _clean_row_value(row, "inheritance")
        cls = _clean_row_value(row, "classification")
        condition = _clean_row_value(row, "condition")

        chunks = [
            f"{index}. Gene: {gene}",
            f"Transcrito: {transcript}",
            f"Variante: {var_c} {var_p}".strip(),
            f"dbSNP: {dbsnp}",
            f"Zigosidade: {zyg}",
            f"Herança: {inh}",
            f"Classificação: {cls}",
        ]
        if condition:
            chunks.append(f"Condição: {condition}")
        lines.append("; ".join(chunks))
    return "\n\n".join(lines).strip()


def _format_cnv_rows_for_overflow(rows):
    lines = []
    for index, row in enumerate(rows or [], start=1):
        cnv_type = _clean_row_value(row, "cnv_type")
        coordinate = _clean_row_value(row, "coordinate")
        region = _clean_row_value(row, "region")
        zyg = _clean_row_value(row, "zygosity")
        cls = _clean_row_value(row, "classification")
        chunks = [
            f"{index}. CNV: {cnv_type}",
            f"Coordenada: {coordinate}",
            f"Região: {region}",
            f"Zigosidade: {zyg}",
            f"Classificação: {cls}",
        ]
        lines.append("; ".join(chunks))
    return "\n\n".join(lines).strip()


def _build_results_table(layout, row):
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
        ["Gene", "Variante", "dbSNP", "Zigosidade", "Herança", "Classificação"],
        [
            "",
            Paragraph(
                f"{_clean_row_value(row, 'variant_c')}<br/><nobr>{_clean_row_value(row, 'variant_p')}</nobr>",
                cell_style,
            ),
            Paragraph(_clean_row_value(row, "dbsnp"), cell_style),
            Paragraph(_clean_row_value(row, "zygosity"), cell_style),
            Paragraph(_clean_row_value(row, "inheritance"), cell_style),
            Paragraph(_clean_row_value(row, "classification"), cell_style),
        ]
    ]
    spec = layout.tables["results"]
    table = Table(
        data,
        colWidths=[w * mm for w in spec.col_widths],
        rowHeights=[5.2 * mm, (spec.row_height - 5.2) * mm],
    )
    table.setStyle(_table_style(layout))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), PURPLE),
                ("FONTNAME", (0, 0), (-1, 0), layout.font_bold),
                ("FONTSIZE", (0, 0), (-1, 0), 8.3),
                ("BACKGROUND", (0, 1), (0, 1), PURPLE),
                ("VALIGN", (0, 1), (0, 1), "MIDDLE"),
                ("ALIGN", (0, 1), (0, 1), "CENTER"),
                ("TEXTCOLOR", (0, 1), (0, 1), Color(1, 1, 1)),
                ("TOPPADDING", (0, 1), (-1, 1), 0.0),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 0.2),
                ("LEFTPADDING", (0, 1), (-1, 1), 0.3),
                ("RIGHTPADDING", (0, 1), (-1, 1), 0.3),
            ]
        )
    )
    return table


def _build_vus_table(layout, row):
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
        ["Gene", "Variante", "dbSNP", "Zigosidade", "Herança", "Classificação"],
        [
            Paragraph(
                f"<b>{_clean_row_value(row, 'gene')}</b><br/><nobr>{_clean_row_value(row, 'transcript')}</nobr>",
                gene_style,
            ),
            Paragraph(
                f"{_clean_row_value(row, 'variant_c')} <nobr>{_clean_row_value(row, 'variant_p')}</nobr>",
                cell_style,
            ),
            Paragraph(_clean_row_value(row, "dbsnp"), cell_style),
            Paragraph(_clean_row_value(row, "zygosity"), cell_style),
            Paragraph(_clean_row_value(row, "inheritance"), cell_style),
            Paragraph(_clean_row_value(row, "classification"), cell_style),
        ]
    ]
    spec = layout.tables["vus"]
    table = Table(
        data,
        colWidths=[w * mm for w in spec.col_widths],
        rowHeights=[5.2 * mm, (spec.row_height - 5.2) * mm],
    )
    table.setStyle(_table_style(layout))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), PURPLE),
                ("FONTNAME", (0, 0), (-1, 0), layout.font_bold),
                ("FONTSIZE", (0, 0), (-1, 0), 8.2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0.2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0.2),
                ("TOPPADDING", (0, 0), (-1, -1), 0.2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4),
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


def draw_footer(c, layout, context, page_number=None, page_total=6):
    # Atualiza apenas paginação do rodapé fixo.
    # Limpa a área onde o PNG traz "Página 1 de 6" e escreve o valor correto.
    c.saveState()
    c.setFillColor(BG_PAGE)
    c.rect(150.0 * mm, _y_from_top(layout, 261.8, 10.5), 40.5 * mm, 10.5 * mm, stroke=0, fill=1)
    if page_number is not None:
        c.setFillColor(PURPLE)
        c.setFont(layout.font_regular, 11.8)
        c.drawRightString(179.0 * mm, _y_from_top(layout, 265.0, 4.8), f"Página {page_number} de {page_total}")
        c.setFont(layout.font_regular, 14.4)
        c.drawString(180.6 * mm, _y_from_top(layout, 265.2, 4.8), ">>")
    c.restoreState()


def _draw_table(c, layout, spec_key, table):
    spec = layout.tables[spec_key]
    table_x = spec.x * mm
    table_y = (layout.page_height - spec.y - spec.row_height) * mm
    table.wrapOn(c, 0, 0)
    table.drawOn(c, table_x, table_y)


def _draw_results_gene_centered(c, layout, row):
    spec = layout.tables["results"]
    header_h_mm = 5.2
    data_h_mm = spec.row_height - header_h_mm
    x = spec.x * mm
    y = (layout.page_height - spec.y - spec.row_height) * mm
    w = spec.col_widths[0] * mm
    cx = x + (w / 2.0)
    cy = y + ((data_h_mm * mm) / 2.0)

    gene = _clean_row_value(row, "gene")
    transcript = _clean_row_value(row, "transcript")
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


def _append_overflow_block(blocks, title, text):
    content = str(text or "").strip()
    if not content:
        return
    blocks.append((str(title or "Continuação"), content))


def _draw_overflow_pages(c, layout, context, blocks):
    for title, block_text in blocks:
        remaining = block_text.strip()
        first_page = True
        while remaining:
            _draw_page_shell(c, layout, 7)
            _draw_header(c, layout, context)
            _draw_section_box(c, layout, 10.5, 68.0, 168.0, 183.0, title)
            page_title = title if first_page else f"{title} (continuação)"
            _draw_paragraph(c, layout, "overflow.title", page_title)
            fit_text, overflow = _split_text_to_fit(layout, "overflow.body", remaining)
            if fit_text:
                _draw_paragraph(c, layout, "overflow.body", fit_text)
            elif overflow == remaining:
                # Safety guard for unexpected no-fit cases with very long tokens.
                break
            draw_footer(c, layout, context, page_number=None)
            c.showPage()
            remaining = overflow.strip()
            first_page = False


def render_template_b_pdf(context):
    _register_fonts()
    layout = get_layout()
    has_front_cover = bool(finders.find("capa.png"))
    has_back_cover = bool(finders.find("capa-rodape.png"))
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=portrait((layout.page_width * mm, layout.page_height * mm)))
    overflow_blocks = []

    main_table_mode = str(context.get("main_table_mode", "variant") or "variant").strip().lower()
    additional_table_mode = str(context.get("additional_table_mode", "variant") or "variant").strip().lower()
    secondary_table_mode = str(context.get("secondary_table_mode", "variant") or "variant").strip().lower()
    main_variant_rows = _get_main_variant_rows(context)
    additional_variant_rows = _get_additional_variant_rows(context)
    secondary_variant_rows = context.get("secondary_variant_rows") if isinstance(context.get("secondary_variant_rows"), list) else []
    main_cnv_rows = _get_cnv_rows(context, "main_cnv_rows")
    additional_cnv_rows = _get_cnv_rows(context, "additional_cnv_rows")
    secondary_cnv_rows = _get_cnv_rows(context, "secondary_cnv_rows")

    # Page 1 (cover)
    _draw_page_shell(c, layout, 1)
    c.saveState()
    c.setFillColor(PURPLE)
    if has_front_cover:
        c.setFont(layout.font_regular, 13.0)
        c.drawString(21.0 * mm, _y_from_top(layout, 108.0, 5.0), "LAUDO CLÍNICO")
        c.setFont(layout.font_bold, 11.2)
        c.drawString(21.0 * mm, _y_from_top(layout, 117.5, 5.0), context.get("exam_name", ""))
    else:
        c.setFont(layout.font_regular, 13.0)
        c.drawString(35.0 * mm, _y_from_top(layout, 122.0, 5.0), "LAUDO CLÍNICO")
        c.setFont(layout.font_bold, 11.6)
        c.drawString(35.0 * mm, _y_from_top(layout, 131.2, 5.0), context.get("exam_name", ""))
    c.restoreState()
    _draw_paragraph(c, layout, "p1.name", f"<b>Nome:</b> {context.get('patient_name','')}")
    _draw_paragraph(c, layout, "p1.birth", f"<b>Data de Nascimento:</b> {context.get('patient_birth_date_cover','')}")
    _draw_paragraph(c, layout, "p1.code", f"<b>Código ID:</b> {context.get('patient_code_cover','')}")
    c.showPage()

    # Page 2
    _draw_page_shell(c, layout, 2)
    _draw_section_box(c, layout, 10.5, 67.2, 168.0, 36.0, "DADOS")
    _draw_section_box(c, layout, 10.5, 121.5, 168.0, 16.5, "RESULTADOS")
    _draw_round_rect(c, layout, 10.5, 149.2, 168.0, 27.6, radius_mm=1.8, stroke=1, fill=0)
    _draw_section_box(c, layout, 10.5, 187.0, 168.0, 50.0, "INTERPRETAÇÃO")
    _draw_header(c, layout, context)
    requester_line = f"<b>Solicitante:</b>&nbsp;{context.get('requester_display') or context.get('requester_name','')}"
    sample_line = f"<b>Amostra:</b>&nbsp;{context.get('sample_display') or context.get('sample_description','')}"
    clinical_indication = (context.get("clinical_indication") or "").strip()
    data_lines = [requester_line, sample_line]
    if clinical_indication:
        data_lines.append(f"<b>Indicação clínica:</b>&nbsp;{clinical_indication}")
    _draw_paragraph(c, layout, "p2.data", "\n".join(data_lines))
    _draw_label_with_bold_value(
        c,
        layout,
        "p2.exam",
        "Nome do exame: ",
        context.get("exam_name", ""),
        min_font_size=8.4,
    )
    result_intro = (
        context.get("main_result_intro")
        or "Foi identificada uma variante clinicamente relevante no gene TP53."
    )
    _draw_paragraph(c, layout, "p2.results", result_intro)
    _draw_paragraph(c, layout, "p2.condition", f"Condição: {context.get('main_condition','')}")
    inheritance_legend = (context.get("main_inheritance_legend") or "").strip()
    if inheritance_legend:
        _draw_paragraph(c, layout, "p2.inheritance_legend", inheritance_legend)
    interpretation_source = context.get("interpretation_text_rendered", "") or context.get("interpretation_text", "")
    interpretation_p2, interpretation_remaining = _split_text_to_fit(
        layout,
        "p2.interpretation",
        interpretation_source,
    )
    if interpretation_p2:
        _draw_paragraph(c, layout, "p2.interpretation", interpretation_p2)
    if main_table_mode == "variant" and main_variant_rows:
        _draw_table(c, layout, "results", _build_results_table(layout, main_variant_rows[0]))
        _draw_results_gene_centered(c, layout, main_variant_rows[0])
    draw_footer(c, layout, context, page_number=1, page_total=6)
    c.showPage()

    # Page 3
    _draw_page_shell(c, layout, 3)
    _draw_section_box(c, layout, 10.5, 68.0, 168.0, 87.5, "INTERPRETAÇÃO")
    _draw_section_box(c, layout, 10.5, 174.0, 168.0, 33.5, "ACHADOS ADICIONAIS")
    _draw_round_rect(c, layout, 10.5, 217.0, 168.0, 18.3, radius_mm=1.8, stroke=1, fill=0)
    _draw_header(c, layout, context)
    interpretation_p3, interpretation_overflow = _split_text_to_fit(
        layout,
        "p3.interpretation",
        interpretation_remaining,
    )
    if interpretation_p3:
        _draw_paragraph(c, layout, "p3.interpretation", interpretation_p3)

    additional_text = context.get("additional_findings_text_rendered", "") or context.get("additional_findings_text", "")
    additional_p3, additional_overflow = _split_text_to_fit(layout, "p3.additional", additional_text)
    if additional_p3:
        _draw_paragraph(c, layout, "p3.additional", additional_p3)
    if additional_table_mode == "variant" and additional_variant_rows:
        _draw_table(c, layout, "vus", _build_vus_table(layout, additional_variant_rows[0]))
    draw_footer(c, layout, context, page_number=2, page_total=6)
    c.showPage()

    # Page 4
    _draw_page_shell(c, layout, 4)
    _draw_section_box(c, layout, 10.5, 68.0, 168.0, 63.5, "GENES ANALISADOS")
    _draw_header(c, layout, context)
    genes_text = context.get("genes_analyzed_list", "")
    genes_p4, genes_overflow = _split_text_to_fit(layout, "p4.genes", genes_text)
    if genes_p4:
        _draw_paragraph(c, layout, "p4.genes", genes_p4)
    draw_footer(c, layout, context, page_number=3, page_total=6)
    c.showPage()

    # Page 5
    _draw_page_shell(c, layout, 5)
    _draw_section_box(c, layout, 10.5, 68.0, 168.0, 59.5, "NOTAS")
    _draw_section_box(c, layout, 10.5, 141.0, 168.0, 23.5, "RECOMENDAÇÕES")
    _draw_section_box(c, layout, 10.5, 184.0, 168.0, 27.5, "MÉTRICAS")
    _draw_header(c, layout, context)
    metrics_mode = str(context.get("metrics_mode", "panel") or "panel").strip().lower()
    if metrics_mode == "exome_mito":
        nuc_base = (context.get("metrics_nuclear_base") or "30x").strip() or "30x"
        mito_base = (context.get("metrics_mito_base") or "100x").strip() or "100x"
        _draw_paragraph(c, layout, "p5.metrics.title", "DNA Nuclear")
        _draw_paragraph(
            c,
            layout,
            "p5.metrics.label_mean",
            f"% da região alvo com cobertura maior ou igual a {nuc_base}:",
        )
        _draw_paragraph(c, layout, "p5.metrics.label_50x", f"% da região alvo com cobertura maior ou igual a {mito_base}:")
        _draw_paragraph(c, layout, "p5.metrics.note", "DNA Mitocondrial")
        _draw_single_line_fitted(c, layout, "p5.metrics.mean", context.get("metrics_nuclear_percent", ""), min_font_size=8.2)
        _draw_single_line_fitted(c, layout, "p5.metrics.50x", context.get("metrics_mito_percent", ""), min_font_size=8.2)
    else:
        metrics_base = (context.get("metrics_coverage_base") or "50x").strip() or "50x"
        _draw_paragraph(c, layout, "p5.metrics.title", "DNA Nuclear")
        _draw_paragraph(c, layout, "p5.metrics.label_mean", "Cobertura média da região alvo:")
        _draw_paragraph(c, layout, "p5.metrics.label_50x", f"% da região alvo com cobertura maior ou igual a {metrics_base}:")
        _draw_paragraph(c, layout, "p5.metrics.note", "Região alvo refere-se a região codificante e sítios de splicing dos genes analisados.")
        _draw_single_line_fitted(c, layout, "p5.metrics.mean", context.get("metrics_coverage_mean", ""), min_font_size=8.2)
        _draw_single_line_fitted(c, layout, "p5.metrics.50x", context.get("metrics_coverage_50x", ""), min_font_size=8.2)
    recommendations_overflow = ""
    rec_text = context.get("recommendations_text_rendered", "") or context.get("recommendations_text", "")
    rec_fit, recommendations_overflow = _split_text_to_fit(layout, "p5.recommendations", rec_text)
    if rec_fit:
        _draw_paragraph(c, layout, "p5.recommendations", rec_fit)
    notes_source = (
        context.get("secondary_findings_text_rendered")
        or context.get("notes_text_rendered")
        or context.get("secondary_findings_text")
        or context.get("notes_text", "")
    )
    notes_text = re.sub(r"\s*\n+\s*", " ", (notes_source or "").strip())
    notes_text = re.sub(r"\s{2,}", " ", notes_text)
    notes_fit, notes_overflow = _split_text_to_fit(layout, "p5.notes", notes_text)
    if notes_fit:
        c.saveState()
        c.setFillColor(PURPLE)
        c.setFont(layout.font_bold, 9.0)
        c.drawString(13.6 * mm, _y_from_top(layout, 84.2, 3.8), "ACHADOS SECUNDÁRIOS")
        c.restoreState()
        _draw_paragraph(c, layout, "p5.notes", f"\n{notes_fit}")
    draw_footer(c, layout, context, page_number=4, page_total=6)
    c.showPage()

    # Page 6
    _draw_page_shell(c, layout, 6)
    _draw_section_box(c, layout, 10.5, 68.0, 168.0, 47.0, "METODOLOGIA")
    _draw_section_box(c, layout, 10.5, 124.0, 168.0, 58.0, "CONSIDERAÇÕES E LIMITAÇÕES")
    _draw_section_box(c, layout, 10.5, 183.0, 168.0, 31.0, "OBSERVAÇÕES")
    _draw_header(c, layout, context)
    methodology_text = context.get("methodology_text_rendered", "") or context.get("methodology_text", "")
    methodology_fit, methodology_overflow = _split_text_to_fit(
        layout,
        "p6.methodology",
        _sanitize_methodology_text(methodology_text),
    )
    if methodology_fit:
        _draw_paragraph(c, layout, "p6.methodology", methodology_fit)
    limitations_fit, limitations_overflow = _split_text_to_fit(
        layout,
        "p6.limitations",
        context.get("limitations_text", ""),
    )
    if limitations_fit:
        _draw_paragraph(c, layout, "p6.limitations", limitations_fit)
    observations_fit, observations_overflow = _split_text_to_fit(
        layout,
        "p6.observations",
        context.get("observations_text", ""),
    )
    if observations_fit:
        _draw_paragraph(c, layout, "p6.observations", observations_fit)
    draw_footer(c, layout, context, page_number=5, page_total=6)
    c.showPage()

    # Page 7
    _draw_page_shell(c, layout, 7)
    _draw_round_rect(c, layout, 10.5, 68.0, 168.0, 185.0, radius_mm=2.2, stroke=1, fill=0)
    _draw_header(c, layout, context)
    observations_p7_fit, observations_p7_overflow = _split_text_to_fit(
        layout,
        "p7.observations",
        observations_overflow,
    )
    if observations_p7_fit:
        _draw_paragraph(c, layout, "p7.observations", observations_p7_fit)
    c.saveState()
    c.setFillColor(PURPLE)
    c.setFont(layout.font_bold, 9.4)
    c.drawString(12.9 * mm, _y_from_top(layout, 104.1, 3.8), "REFERÊNCIAS BIBLIOGRÁFICAS")
    c.restoreState()
    references_fit, references_overflow = _split_text_to_fit(
        layout,
        "p7.references",
        context.get("references_text", ""),
    )
    if references_fit:
        _draw_paragraph(c, layout, "p7.references", references_fit)
    draw_footer(c, layout, context, page_number=6, page_total=6)
    c.showPage()

    if main_table_mode == "variant" and len(main_variant_rows) > 1:
        _append_overflow_block(
            overflow_blocks,
            "Resultado principal - linhas adicionais",
            _format_variant_rows_for_overflow(main_variant_rows[1:]),
        )
    if main_table_mode == "cnv" and main_cnv_rows:
        _append_overflow_block(
            overflow_blocks,
            "Resultado principal - CNV",
            _format_cnv_rows_for_overflow(main_cnv_rows),
        )
    if additional_table_mode == "variant" and len(additional_variant_rows) > 1:
        _append_overflow_block(
            overflow_blocks,
            "Achados adicionais - linhas adicionais",
            _format_variant_rows_for_overflow(additional_variant_rows[1:]),
        )
    if additional_table_mode == "cnv" and additional_cnv_rows:
        _append_overflow_block(
            overflow_blocks,
            "Achados adicionais - CNV",
            _format_cnv_rows_for_overflow(additional_cnv_rows),
        )
    if secondary_table_mode == "variant" and secondary_variant_rows:
        _append_overflow_block(
            overflow_blocks,
            "Achados secundarios - tabela",
            _format_variant_rows_for_overflow(secondary_variant_rows),
        )
    if secondary_table_mode == "cnv" and secondary_cnv_rows:
        _append_overflow_block(
            overflow_blocks,
            "Achados secundarios - CNV",
            _format_cnv_rows_for_overflow(secondary_cnv_rows),
        )

    _append_overflow_block(overflow_blocks, "Interpretação", interpretation_overflow)
    _append_overflow_block(overflow_blocks, "Achados adicionais", additional_overflow)
    _append_overflow_block(overflow_blocks, "Genes analisados", genes_overflow)
    _append_overflow_block(overflow_blocks, "Achados secundarios / notas", notes_overflow)
    _append_overflow_block(overflow_blocks, "Recomendações", recommendations_overflow)
    _append_overflow_block(overflow_blocks, "Metodologia", methodology_overflow)
    _append_overflow_block(overflow_blocks, "Considerações e limitações", limitations_overflow)
    _append_overflow_block(overflow_blocks, "Observações", observations_p7_overflow)
    _append_overflow_block(overflow_blocks, "Referências", references_overflow)
    _draw_overflow_pages(c, layout, context, overflow_blocks)

    # Page 8 (institutional back cover)
    _draw_page_shell(c, layout, 8)
    if not has_back_cover:
        _draw_image(
            c,
            layout,
            "editor/img/elements/logo_bioma_element_cropped.png",
            x_mm=63.0,
            y_mm=196.0,
            w_mm=66.0,
            h_mm=24.0,
            preserve=True,
        )
        c.saveState()
        c.setFillColor(PURPLE)
        c.setFont(layout.font_bold, 12.8)
        c.drawCentredString((layout.page_width / 2.0) * mm, _y_from_top(layout, 231.0, 5.0), "www.biomagenetics.com.br")
        c.setFont(layout.font_regular, 9.6)
        c.drawCentredString((layout.page_width / 2.0) * mm, _y_from_top(layout, 241.0, 4.0), "Rua Luigi Galvani, 146 - Itaim Bibi, São Paulo, SP")
        c.restoreState()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()
