"""Generate the accessible-color Figure 1 pipeline diagram as SVG."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from math import hypot
from pathlib import Path

import fitz


WIDTH = 3000
HEIGHT = 1500


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    width: int
    height: int
    title: str
    lines: tuple[str, ...]
    fill: str = "#E8F1F5"
    title_size: int = 34
    body_size: int = 29


BOXES = (
    Box(60, 220, 300, 200, "Synthetic screens", ("20 mock mobile UIs", "Screenshot source"), "#DCEEFF", title_size=31, body_size=27),
    Box(420, 220, 380, 200, "Command generation", ("Thai and Thai-English", "Four instruction tiers"), "#E8F1F5", title_size=31, body_size=27),
    Box(860, 220, 300, 200, "TTS synthesis", ("Synthetic speech", "Multiple voices"), "#E8F1F5", title_size=31, body_size=27),
    Box(1220, 220, 340, 200, "ASR transcription", ("Whisper large-v3", "Typhoon ASR"), "#E8F1F5", title_size=31, body_size=27),
    Box(1660, 190, 430, 240, "Raw-ASR grounding", ("Inputs: screenshot", "+ raw ASR transcript", "Models: G1 and G2"), "#D9EAF7", title_size=32, body_size=26),
    Box(
        1600,
        650,
        500,
        310,
        "Fixed correction methods",
        (
            "A  No-screen cleanup",
            "B  Screen string matching",
            "C  Screen-aware aliases",
            "Inputs: ASR transcript",
            "+ visible screen lexicon",
        ),
        "#FFF0C2",
        title_size=32,
        body_size=25,
    ),
    Box(2160, 700, 390, 210, "Corrected grounding", ("Inputs: screenshot", "+ corrected transcript", "Same G1/G2 settings"), "#D9F0E8", title_size=31, body_size=24),
    Box(
        1050,
        1080,
        1000,
        300,
        "Transcript evaluation",
        (
            "ASR: CER, Thai-tokenized WER, loanword error",
            "Correction: recovery rate and false correction rate",
            "Computed directly from transcript records",
        ),
        "#E8E0F4",
        title_size=34,
        body_size=27,
    ),
    Box(
        2580,
        390,
        360,
        410,
        "Grounding evaluation",
        (
            "Raw click accuracy",
            "Corrected-run accuracy",
            "Changed vs unchanged",
            "Parse/bounds failures",
            "kept in denominator",
        ),
        "#F6DED8",
        title_size=27,
        body_size=23,
    ),
)


ARROWS = (
    ((360, 320), (420, 320), False, "", "#526D82"),
    ((800, 320), (860, 320), False, "", "#526D82"),
    ((1160, 320), (1220, 320), False, "", "#526D82"),
    ((1560, 320), (1600, 320), (1600, 310), (1660, 310), False, "", "#2F6B9A"),
    ((1390, 420), (1390, 805), (1600, 805), False, "", "#9A6700"),
    ((2100, 805), (2160, 805), False, "", "#287A6B"),
    ((2090, 310), (2460, 310), (2460, 500), (2580, 500), False, "", "#2F6B9A"),
    ((2550, 805), (2565, 805), (2565, 690), (2580, 690), False, "", "#287A6B"),
    ((1340, 420), (1340, 1080), False, "", "#66558A"),
    ((1850, 960), (1850, 1080), False, "", "#66558A"),
)


def svg_text(x: int, y: int, text: str, size: int, *, weight: int = 400, anchor: str = "middle", fill: str = "#111111") -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">{escape(text)}</text>'
    )


def svg_box(box: Box) -> str:
    parts = [
        f'<rect x="{box.x}" y="{box.y}" width="{box.width}" height="{box.height}" '
        f'rx="8" fill="{box.fill}" stroke="#222222" stroke-width="3"/>',
    ]
    center_x = box.x + box.width // 2
    title_y = box.y + 52
    parts.append(svg_text(center_x, title_y, box.title, box.title_size, weight=700))
    line_gap = box.body_size + 13
    first_y = title_y + 50
    for index, line in enumerate(box.lines):
        parts.append(svg_text(center_x, first_y + index * line_gap, line, box.body_size))
    return "\n".join(parts)


def svg_arrow(item: tuple[object, ...]) -> str:
    *points, dashed, label, color = item
    point_text = " ".join(f"{x},{y}" for x, y in points)
    dash = ' stroke-dasharray="12 10"' if dashed else ""
    stroke = str(color)
    parts = [
        f'<polyline points="{point_text}" fill="none" stroke="{stroke}" stroke-width="3"'
        f'{dash} stroke-linejoin="round"/>',
    ]
    start_x, start_y = points[-2]
    end_x, end_y = points[-1]
    length = hypot(end_x - start_x, end_y - start_y)
    unit_x = (end_x - start_x) / length
    unit_y = (end_y - start_y) / length
    base_x = end_x - 15 * unit_x
    base_y = end_y - 15 * unit_y
    perp_x = -unit_y * 8
    perp_y = unit_x * 8
    arrow_points = (
        f"{end_x},{end_y} "
        f"{base_x + perp_x:.1f},{base_y + perp_y:.1f} "
        f"{base_x - perp_x:.1f},{base_y - perp_y:.1f}"
    )
    parts.append(f'<polygon points="{arrow_points}" fill="{stroke}"/>')
    if label:
        start_x, start_y = points[0]
        end_x, end_y = points[-1]
        label_x = (start_x + end_x) // 2
        label_y = min(start_y, end_y) - 12
        if abs(end_y - start_y) > 180:
            label_x = max(start_x, end_x) + 12
            label_y = (start_y + end_y) // 2
        parts.append(svg_text(label_x, label_y, str(label), 22, anchor="middle", fill="#444444"))
    return "\n".join(parts)


def build_svg() -> str:
    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        "<defs>",
        '<marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">',
        '<path d="M 0 0 L 10 4 L 0 8 z" fill="#555555"/>',
        "</marker>",
        "</defs>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        svg_text(WIDTH // 2, 58, "ThaiVoice-GUIBench: benchmark, correction, and evaluation pipeline", 48, weight=700),
        svg_text(WIDTH // 2, 103, "Original 20-screen controlled diagnostic dataset", 29, fill="#444444"),
        '<rect x="35" y="150" width="1535" height="330" rx="10" fill="#F7FAFC" stroke="#D7E1E8" stroke-width="2"/>',
        '<rect x="1580" y="130" width="1380" height="360" rx="10" fill="#F4F9FD" stroke="#C8DDEA" stroke-width="2"/>',
        '<rect x="1540" y="580" width="1420" height="430" rx="10" fill="#FFFAEC" stroke="#E8D69A" stroke-width="2"/>',
    ]
    body.extend(svg_arrow(arrow) for arrow in ARROWS)
    body.extend(svg_box(box) for box in BOXES)

    body.extend(
        [
            svg_text(75, 190, "DATA AND SPEECH PIPELINE", 21, weight=700, anchor="start", fill="#526D82"),
            svg_text(1620, 170, "RAW ASR PATH", 21, weight=700, anchor="start", fill="#2F6B9A"),
            svg_text(1580, 625, "FIXED CORRECTION PATH", 21, weight=700, anchor="start", fill="#9A6700"),
            '<rect x="2110" y="1080" width="830" height="300" rx="8" fill="#F3F5F7" '
            'stroke="#68727D" stroke-width="3" stroke-dasharray="10 8"/>',
            svg_text(2525, 1135, "Interpretation limitation", 31, weight=700),
            svg_text(2525, 1185, "Raw and corrected grounding are", 25),
            svg_text(2525, 1222, "independent inference runs.", 25),
            svg_text(2525, 1265, "Unchanged prompts quantify rerun variability.", 23),
            svg_text(2525, 1302, "Pooled differences are not purely causal effects.", 23),
            svg_text(60, 1450, "Grounding input: screenshot + transcript only. Target IDs, target boxes, and gold answers are never provided.", 24, anchor="start", fill="#444444"),
            "</svg>",
        ]
    )
    return "\n".join(body) + "\n"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    figure_dir = repo_root / "figures"
    svg_path = figure_dir / "figure1_pipeline_diagram.svg"
    png_path = figure_dir / "figure1_pipeline_diagram.png"
    pdf_path = figure_dir / "figure1_pipeline_diagram.pdf"
    figure_dir.mkdir(parents=True, exist_ok=True)

    svg = build_svg()
    svg_path.write_text(svg, encoding="utf-8")

    document = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    pdf_path.write_bytes(document.convert_to_pdf())
    page = document[0]
    scale = WIDTH / page.rect.width
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    pixmap.save(png_path)

    print(f"Wrote {svg_path}")
    print(f"Wrote {png_path}")
    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
