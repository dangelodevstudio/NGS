"""Layout constants for ReportLab PDF rendering (Template B)."""
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class FieldSpec:
    x: float
    y: float
    w: float
    h: float
    font_size: float
    leading: float
    align: int = 0
    padding_x: float = 0.0
    padding_y: float = 0.0
    color: str = "gray"
    font_name: str = "regular"


@dataclass(frozen=True)
class TableSpec:
    x: float
    y: float
    row_height: float
    col_widths: List[float]


@dataclass(frozen=True)
class ReportLayout:
    page_width: float
    page_height: float
    padding_x: float
    padding_y: float
    font_regular: str
    font_bold: str
    fields: Dict[str, FieldSpec]
    tables: Dict[str, TableSpec]


def _field(x, y, w, h, font_size, leading, **kwargs):
    return FieldSpec(x=x, y=y, w=w, h=h, font_size=font_size, leading=leading, **kwargs)


def _table(x, y, row_height, col_widths):
    return TableSpec(x=x, y=y, row_height=row_height, col_widths=col_widths)


def get_layout() -> ReportLayout:
    # Page size from template images (190.5mm x 275mm).
    page_width = 190.5
    page_height = 275.0
    padding_x = 3.4
    padding_y = 2.0

    fields = {
        # Page 1 cover
        "p1.name": _field(26.05, 135.16, 140.10, 8.00, 16, 19.0, color="purple", font_name="bold"),
        "p1.birth": _field(24.89, 148.75, 140.10, 6.00, 14, 15.0, color="purple", font_name="bold"),
        "p1.code": _field(24.89, 155.73, 140.10, 6.00, 14, 15.0, color="purple", font_name="bold"),

        # Header (pages 2-7)
        "header.name": _field(72.25, 13.72, 101.00, 6.00, 14, 16.0, color="purple", font_name="bold"),
        "header.birth": _field(72.25, 19.16, 101.00, 6.00, 11, 13.0, color="purple"),
        "header.sex": _field(72.25, 23.82, 101.00, 6.00, 11, 13.0, color="purple"),
        "header.code": _field(72.25, 28.81, 101.00, 6.00, 11, 13.0, color="purple"),
        "header.entry": _field(72.25, 33.55, 101.00, 6.00, 11, 13.0, color="purple"),
        "header.release": _field(72.25, 38.21, 101.00, 6.00, 11, 13.0, color="purple"),

        # Page 2 content
        "p2.data": _field(13.61, 78.01, 164.97, 25.60, 9.8, 10.8, padding_x=2.0, padding_y=0.8, align=0),
        "p2.requester": _field(13.61, 78.01, 164.91, 4.23, 12, 11.0),
        "p2.sample": _field(13.61, 82.24, 164.97, 4.23, 12, 11.0),
        "p2.clinical": _field(13.61, 86.48, 169.16, 11.10, 10.0, 11.0, padding_x=1.2, padding_y=0.5, align=4),
        "p2.exam": _field(13.61, 99.18, 160.91, 4.23, 12, 11.0),
        "p2.results": _field(12.99, 128.00, 164.02, 11.10, 10.5, 13.0, padding_x=padding_x, padding_y=padding_y, align=4),
        "p2.condition": _field(39.40, 172.16, 135.25, 4.30, 10, 12.0),
        "p2.interpretation": _field(13.08, 200.14, 163.63, 34.30, 10.0, 10.5, padding_x=padding_x, padding_y=0.0, align=4),

        # Page 3 content
        "p3.interpretation": _field(12.70, 72.22, 165.10, 83.33, 10.0, 10.5, padding_x=padding_x, padding_y=0.0, align=4),
        "p3.additional": _field(12.77, 181.90, 164.38, 22.04, 10.0, 11.0, padding_x=padding_x, padding_y=0.0, align=4),

        # Page 4 content
        "p4.genes": _field(12.90, 82.99, 164.24, 47.00, 9.0, 11.0, padding_x=3.4, padding_y=0.0, align=4),

        # Page 5 content
        "p5.notes": _field(13.33, 84.00, 164.34, 43.50, 9.0, 9.7, padding_x=1.8, padding_y=1.0, align=0),
        "p5.recommendations": _field(13.44, 146.42, 164.53, 17.37, 9.3, 10.0, padding_x=2.2, padding_y=0.8, align=4),
        "p5.metrics.title": _field(15.13, 189.19, 117.07, 4.67, 11.0, 13.0, color="purple", font_name="bold"),
        "p5.metrics.label_mean": _field(15.13, 192.20, 119.06, 4.80, 9.3, 10.0, color="purple", font_name="bold"),
        "p5.metrics.label_50x": _field(15.13, 198.55, 119.06, 4.80, 9.3, 10.0, color="purple", font_name="bold"),
        "p5.metrics.note": _field(15.13, 204.00, 118.88, 3.80, 8.0, 8.6, color="purple"),
        "p5.metrics.mean": _field(156.49, 191.70, 20.00, 5.00, 9.8, 10.0, align=1),
        "p5.metrics.50x": _field(156.49, 203.25, 20.00, 5.00, 9.8, 10.0, align=1),

        # Page 6 content
        "p6.methodology": _field(13.11, 75.99, 163.84, 38.53, 10.5, 11.5, padding_x=1.2, padding_y=1.0, align=4),

        # Footer (internal pages: 2-7)
        "footer.analyst": _field(27.21, 248.70, 145.14, 4.10, 9.0, 10.0, color="purple", font_name="bold"),
        "footer.tech": _field(27.21, 252.40, 145.14, 4.10, 9.0, 10.0, color="purple", font_name="bold"),
        "footer.md": _field(27.21, 256.10, 145.14, 4.10, 9.0, 10.0, color="purple", font_name="bold"),
        "footer.director": _field(27.21, 259.81, 145.14, 4.10, 9.0, 10.0, color="purple", font_name="bold"),
    }

    tables = {
        # Results table (page 2). y measured from top of page.
        "results": _table(
            x=12.53,
            y=151.72,
            row_height=14.20,
            col_widths=[24.384, 35.899, 25.061, 24.892, 26.416, 27.432],
        ),
        # VUS table (page 3).
        "vus": _table(
            x=12.53,
            y=217.00,
            row_height=17.00,
            col_widths=[24.384, 35.899, 25.061, 24.892, 26.416, 27.432],
        ),
    }

    return ReportLayout(
        page_width=page_width,
        page_height=page_height,
        padding_x=padding_x,
        padding_y=padding_y,
        font_regular="RedHatDisplay",
        font_bold="RedHatDisplayBold",
        fields=fields,
        tables=tables,
    )
