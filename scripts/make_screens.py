"""Generate deterministic synthetic GUI screens for ThaiVoice-GUIBench."""

from __future__ import annotations

import argparse
import json
import random
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DOMAINS = ("mock_finance", "shopping", "settings", "messaging")
LANGUAGE_CYCLE = ("en", "th", "mixed", "paired", "th")

FONT_CANDIDATES = (
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/LeelawUI.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Thonburi.ttc",
    "/System/Library/Fonts/ThonburiUI.ttc",
    "/System/Library/Fonts/Supplemental/Tahoma.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


@dataclass(frozen=True)
class ElementSpec:
    label: str
    role: str
    language: str
    group: str


@dataclass(frozen=True)
class DomainSpec:
    title_en: str
    title_th: str
    subtitle_en: str
    subtitle_th: str
    primary_en: tuple[str, ...]
    primary_th: tuple[str, ...]
    secondary_en: tuple[str, ...]
    secondary_th: tuple[str, ...]
    tabs_en: tuple[str, ...]
    tabs_th: tuple[str, ...]
    distractor_group: str
    palette: tuple[str, str, str, str]


DOMAIN_SPECS: dict[str, DomainSpec] = {
    "mock_finance": DomainSpec(
        title_en="Mock Wallet",
        title_th="กระเป๋าจำลอง",
        subtitle_en="Synthetic finance practice screen",
        subtitle_th="หน้าฝึกการเงินจำลอง",
        primary_en=("Transfer", "Top up", "Withdraw", "History"),
        primary_th=("โอนเงิน", "เติมเงิน", "ถอนเงิน", "ประวัติ"),
        secondary_en=("Pay bill", "Savings", "Cards", "Rewards"),
        secondary_th=("จ่ายบิล", "เงินออม", "บัตร", "รางวัล"),
        tabs_en=("Home", "Scan", "Accounts", "Help"),
        tabs_th=("หน้าแรก", "สแกน", "บัญชี", "ช่วยเหลือ"),
        distractor_group="money_actions",
        palette=("#f4fbf8", "#0f766e", "#dff5ee", "#12312e"),
    ),
    "shopping": DomainSpec(
        title_en="Market Demo",
        title_th="ตลาดจำลอง",
        subtitle_en="Synthetic shopping task screen",
        subtitle_th="หน้าฝึกซื้อของจำลอง",
        primary_en=("Search", "Sort", "Filter", "Promotion"),
        primary_th=("ค้นหา", "เรียงลำดับ", "ตัวกรอง", "โปรโมชัน"),
        secondary_en=("Buy now", "Add cart", "Lowest price", "Wishlist"),
        secondary_th=("ซื้อเลย", "ใส่ตะกร้า", "ราคาถูกที่สุด", "รายการโปรด"),
        tabs_en=("Shop", "Cart", "Deals", "Profile"),
        tabs_th=("ร้านค้า", "รถเข็น", "ดีล", "โปรไฟล์"),
        distractor_group="shopping_actions",
        palette=("#fff8f1", "#b45309", "#ffedd5", "#3b2412"),
    ),
    "settings": DomainSpec(
        title_en="Device Panel",
        title_th="แผงอุปกรณ์",
        subtitle_en="Synthetic settings control screen",
        subtitle_th="หน้าฝึกตั้งค่าจำลอง",
        primary_en=("Settings", "Language", "Privacy", "Notifications"),
        primary_th=("ตั้งค่า", "ภาษา", "ความเป็นส่วนตัว", "การแจ้งเตือน"),
        secondary_en=("Display", "Security", "Storage", "Accessibility"),
        secondary_th=("หน้าจอ", "ความปลอดภัย", "พื้นที่เก็บข้อมูล", "การช่วยการเข้าถึง"),
        tabs_en=("General", "Network", "Sound", "About"),
        tabs_th=("ทั่วไป", "เครือข่าย", "เสียง", "เกี่ยวกับ"),
        distractor_group="settings_controls",
        palette=("#f6f7fb", "#4f46e5", "#e8eaff", "#1f2347"),
    ),
    "messaging": DomainSpec(
        title_en="Chat Sandbox",
        title_th="แชตจำลอง",
        subtitle_en="Synthetic messaging task screen",
        subtitle_th="หน้าฝึกข้อความจำลอง",
        primary_en=("Send", "Search", "Mute", "Profile"),
        primary_th=("ส่ง", "ค้นหา", "ปิดเสียง", "โปรไฟล์"),
        secondary_en=("New chat", "Archive", "Pin", "Read"),
        secondary_th=("แชตใหม่", "เก็บถาวร", "ปักหมุด", "อ่านแล้ว"),
        tabs_en=("Chats", "Calls", "Groups", "Contacts"),
        tabs_th=("แชต", "โทร", "กลุ่ม", "ผู้ติดต่อ"),
        distractor_group="message_actions",
        palette=("#f8fbff", "#2563eb", "#dbeafe", "#172554"),
    ),
}


SECONDARY_VARIANTS: dict[str, dict[str, tuple[tuple[str, ...], ...]]] = {
    "mock_finance": {
        "en": (
            ("Pay bill", "Savings", "Cards", "Rewards"),
            ("Receipt", "Limits", "Favorites", "Branches"),
            ("Scheduled", "Statements", "Budget", "Support"),
        ),
        "th": (
            ("จ่ายบิล", "เงินออม", "บัตร", "รางวัล"),
            ("สลิป", "วงเงิน", "รายการโปรด", "สาขา"),
            ("ตั้งเวลาจ่าย", "รายการเดินบัญชี", "งบประมาณ", "ช่วยเหลือ"),
        ),
    },
    "shopping": {
        "en": (
            ("Buy now", "Add cart", "Lowest price", "Wishlist"),
            ("Coupon", "Free shipping", "New arrivals", "Track order"),
            ("Buy again", "Today deals", "Compare", "Reviews"),
        ),
        "th": (
            ("ซื้อเลย", "ใส่ตะกร้า", "ราคาถูกที่สุด", "รายการโปรด"),
            ("คูปอง", "ส่งฟรี", "สินค้าใหม่", "ติดตามพัสดุ"),
            ("ซื้อซ้ำ", "ดีลวันนี้", "เปรียบเทียบ", "รีวิวสินค้า"),
        ),
    },
    "settings": {
        "en": (
            ("Display", "Security", "Storage", "Accessibility"),
            ("Battery", "Network", "Sound", "Account"),
            ("Theme", "Backup", "Location", "Quick toggle"),
        ),
        "th": (
            ("หน้าจอ", "ความปลอดภัย", "พื้นที่เก็บข้อมูล", "การช่วยการเข้าถึง"),
            ("แบตเตอรี่", "เครือข่าย", "เสียง", "บัญชี"),
            ("ธีม", "สำรองข้อมูล", "ตำแหน่ง", "สวิตช์ด่วน"),
        ),
    },
    "messaging": {
        "en": (
            ("New chat", "Archive", "Pin", "Read"),
            ("Attach", "Forward", "Star", "Block"),
            ("Drafts", "Mentions", "Unread", "Calls"),
        ),
        "th": (
            ("แชตใหม่", "เก็บถาวร", "ปักหมุด", "อ่านแล้ว"),
            ("แนบไฟล์", "ส่งต่อ", "ติดดาว", "บล็อก"),
            ("ฉบับร่าง", "กล่าวถึง", "ยังไม่ได้อ่าน", "โทร"),
        ),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-per-domain", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=Path, default=Path("data/screens"))
    parser.add_argument("--image-width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--image-height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--report", action="store_true", help="Write SCREEN_GENERATION_REPORT.md")
    return parser.parse_args()


def slugify(label: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-zก-๙]+", "_", label.strip().lower()).strip("_")
    return cleaned or "element"


def language_of(label: str) -> str:
    has_thai = any("\u0e00" <= char <= "\u0e7f" for char in label)
    has_ascii = any("a" <= char.lower() <= "z" for char in label)
    if has_thai and has_ascii:
        return "mixed"
    if has_thai:
        return "th"
    return "en"


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    extra_candidates = (
        "C:/Windows/Fonts/tahomabd.ttf",
        "C:/Windows/Fonts/LeelaUIb.ttf",
        "/System/Library/Fonts/Supplemental/Tahoma Bold.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
    )
    candidates = extra_candidates + FONT_CANDIDATES if bold else FONT_CANDIDATES
    for font_path in candidates:
        path = Path(font_path)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    preferred_size: int,
    min_size: int = 24,
    bold: bool = False,
) -> ImageFont.ImageFont:
    for size in range(preferred_size, min_size - 1, -2):
        font = load_font(size, bold=bold)
        width, _ = text_size(draw, text, font)
        if width <= max_width:
            return font
    return load_font(min_size, bold=bold)


def choose_labels(
    english: tuple[str, ...],
    thai: tuple[str, ...],
    language_mode: str,
) -> tuple[str, ...]:
    if language_mode == "en":
        return english
    if language_mode == "th":
        return thai
    if language_mode == "paired":
        return tuple(label for pair in zip(thai[:2], english[:2]) for label in pair)
    mixed: list[str] = []
    for index, (en_label, th_label) in enumerate(zip(english, thai)):
        mixed.append(th_label if index % 2 == 0 else en_label)
    return tuple(mixed)


def rotate_labels(labels: tuple[str, ...], offset: int) -> tuple[str, ...]:
    if not labels:
        return labels
    offset = offset % len(labels)
    return labels[offset:] + labels[:offset]


def choose_secondary_labels(domain: str, language_mode: str, variant: int) -> tuple[str, ...]:
    variants = SECONDARY_VARIANTS[domain]
    en_labels = variants["en"][variant % len(variants["en"])]
    th_labels = variants["th"][variant % len(variants["th"])]
    return choose_labels(en_labels, th_labels, language_mode)


def build_elements(domain: str, screen_id: str, language_mode: str, variant: int = 0) -> list[ElementSpec]:
    spec = DOMAIN_SPECS[domain]
    primary = rotate_labels(choose_labels(spec.primary_en, spec.primary_th, language_mode), variant)
    secondary = rotate_labels(choose_secondary_labels(domain, language_mode, variant), variant // 2)
    tabs = rotate_labels(choose_labels(spec.tabs_en, spec.tabs_th, language_mode), variant // 3)

    elements: list[ElementSpec] = [
        ElementSpec(label=label, role="button", language=language_of(label), group=spec.distractor_group)
        for label in primary
    ]
    elements.extend(
        ElementSpec(label=label, role="list_item", language=language_of(label), group="secondary_actions")
        for label in secondary
    )
    elements.extend(
        ElementSpec(label=label, role="tab", language=language_of(label), group="bottom_navigation")
        for label in tabs
    )

    # Ensure paired screens visibly contain the Thai and English form of the same concept.
    if language_mode == "paired" and len(elements) < 12:
        for en_label, th_label in zip(spec.primary_en[2:], spec.primary_th[2:]):
            elements.append(
                ElementSpec(
                    label=f"{th_label} / {en_label}",
                    role="button",
                    language="mixed",
                    group=spec.distractor_group,
                )
            )

    return elements


def scaled(value: int, current: int, base: int) -> int:
    return round(value * current / base)


def layout_boxes(width: int, height: int, count: int) -> list[list[int]]:
    margin_x = scaled(72, width, DEFAULT_WIDTH)
    card_gap = scaled(28, width, DEFAULT_WIDTH)
    primary_top = scaled(430, height, DEFAULT_HEIGHT)
    primary_height = scaled(150, height, DEFAULT_HEIGHT)
    card_width = (width - (2 * margin_x) - card_gap) // 2
    boxes: list[list[int]] = []

    for row in range(2):
        for col in range(2):
            x1 = margin_x + col * (card_width + card_gap)
            y1 = primary_top + row * (primary_height + scaled(28, height, DEFAULT_HEIGHT))
            boxes.append([x1, y1, x1 + card_width, y1 + primary_height])

    list_top = scaled(820, height, DEFAULT_HEIGHT)
    list_height = scaled(116, height, DEFAULT_HEIGHT)
    for row in range(4):
        x1 = margin_x
        y1 = list_top + row * (list_height + scaled(24, height, DEFAULT_HEIGHT))
        boxes.append([x1, y1, width - margin_x, y1 + list_height])

    bottom_top = height - scaled(188, height, DEFAULT_HEIGHT)
    tab_width = (width - 2 * margin_x) // 4
    for index in range(4):
        x1 = margin_x + index * tab_width
        boxes.append([x1, bottom_top, x1 + tab_width - scaled(8, width, DEFAULT_WIDTH), height - scaled(58, height, DEFAULT_HEIGHT)])

    while len(boxes) < count:
        extra_index = len(boxes) - 12
        x1 = margin_x
        y1 = scaled(1380, height, DEFAULT_HEIGHT) + extra_index * scaled(112, height, DEFAULT_HEIGHT)
        boxes.append([x1, y1, width - margin_x, min(y1 + scaled(96, height, DEFAULT_HEIGHT), height - scaled(220, height, DEFAULT_HEIGHT))])

    return boxes[:count]


def draw_round_rect(
    draw: ImageDraw.ImageDraw,
    bbox: Iterable[int],
    radius: int,
    fill: str,
    outline: str | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(tuple(bbox), radius=radius, fill=fill, outline=outline, width=width)


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    bbox: list[int],
    text: str,
    fill: str,
    preferred_size: int,
    bold: bool = False,
) -> None:
    padding = 24
    max_width = max(20, bbox[2] - bbox[0] - padding * 2)
    font = fit_font(draw, text, max_width=max_width, preferred_size=preferred_size, bold=bold)
    text_w, text_h = text_size(draw, text, font)
    x = bbox[0] + ((bbox[2] - bbox[0] - text_w) // 2)
    y = bbox[1] + ((bbox[3] - bbox[1] - text_h) // 2)
    draw.text((x, y), text, fill=fill, font=font)


def draw_left_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    fill: str,
    max_width: int,
    preferred_size: int,
    bold: bool = False,
) -> None:
    font = fit_font(draw, text, max_width=max_width, preferred_size=preferred_size, bold=bold)
    draw.text((x, y), text, fill=fill, font=font)


def draw_lexicon_chips(
    draw: ImageDraw.ImageDraw,
    bbox: list[int],
    labels: list[str],
    accent: str,
    ink: str,
    width: int,
    height: int,
) -> None:
    draw_left_text(
        draw,
        bbox[0] + scaled(28, width, DEFAULT_WIDTH),
        bbox[1] + scaled(18, height, DEFAULT_HEIGHT),
        "Screen lexicon",
        accent,
        bbox[2] - bbox[0] - scaled(56, width, DEFAULT_WIDTH),
        scaled(28, height, DEFAULT_HEIGHT),
        bold=True,
    )
    font = load_font(scaled(24, height, DEFAULT_HEIGHT), bold=True)
    chip_x = bbox[0] + scaled(28, width, DEFAULT_WIDTH)
    chip_y = bbox[1] + scaled(66, height, DEFAULT_HEIGHT)
    max_x = bbox[2] - scaled(28, width, DEFAULT_WIDTH)
    chip_gap = scaled(10, width, DEFAULT_WIDTH)
    row_gap = scaled(12, height, DEFAULT_HEIGHT)
    chip_h = scaled(44, height, DEFAULT_HEIGHT)
    padding_x = scaled(18, width, DEFAULT_WIDTH)

    for label in labels:
        label_w, _ = text_size(draw, label, font)
        chip_w = min(label_w + padding_x * 2, max_x - bbox[0] - scaled(56, width, DEFAULT_WIDTH))
        if chip_x + chip_w > max_x:
            chip_x = bbox[0] + scaled(28, width, DEFAULT_WIDTH)
            chip_y += chip_h + row_gap
        if chip_y + chip_h > bbox[3] - scaled(16, height, DEFAULT_HEIGHT):
            break
        chip_bbox = [chip_x, chip_y, chip_x + chip_w, chip_y + chip_h]
        draw_round_rect(
            draw,
            chip_bbox,
            radius=scaled(18, width, DEFAULT_WIDTH),
            fill="#f8fafc",
            outline="#d7dee8",
            width=scaled(1, width, DEFAULT_WIDTH),
        )
        clipped_label = label
        while text_size(draw, clipped_label, font)[0] > chip_w - padding_x * 2 and len(clipped_label) > 1:
            clipped_label = clipped_label[:-2] + "."
        text_w, text_h = text_size(draw, clipped_label, font)
        draw.text(
            (chip_bbox[0] + padding_x, chip_bbox[1] + (chip_h - text_h) // 2),
            clipped_label,
            fill=ink,
            font=font,
        )
        chip_x += chip_w + chip_gap


def screen_title(spec: DomainSpec, language_mode: str) -> tuple[str, str]:
    if language_mode == "en":
        return spec.title_en, spec.subtitle_en
    if language_mode == "th":
        return spec.title_th, spec.subtitle_th
    if language_mode == "paired":
        return f"{spec.title_th} / {spec.title_en}", f"{spec.subtitle_th} / {spec.subtitle_en}"
    return spec.title_th, spec.subtitle_en


def render_screen(
    screen: dict,
    language_mode: str,
    image_path: Path,
) -> None:
    width = screen["width"]
    height = screen["height"]
    spec = DOMAIN_SPECS[screen["domain"]]
    background, accent, soft, ink = spec.palette
    image = Image.new("RGB", (width, height), color=background)
    draw = ImageDraw.Draw(image)

    margin_x = scaled(72, width, DEFAULT_WIDTH)
    title, subtitle = screen_title(spec, language_mode)

    # Header and synthetic phone chrome.
    draw.rounded_rectangle(
        (scaled(44, width, DEFAULT_WIDTH), scaled(28, height, DEFAULT_HEIGHT), width - scaled(44, width, DEFAULT_WIDTH), height - scaled(28, height, DEFAULT_HEIGHT)),
        radius=scaled(56, width, DEFAULT_WIDTH),
        outline="#d7dce5",
        width=scaled(4, width, DEFAULT_WIDTH),
    )
    draw.rectangle((0, 0, width, scaled(120, height, DEFAULT_HEIGHT)), fill=background)
    draw_left_text(draw, margin_x, scaled(160, height, DEFAULT_HEIGHT), title, ink, width - 2 * margin_x, scaled(54, height, DEFAULT_HEIGHT), bold=True)
    draw_left_text(draw, margin_x, scaled(230, height, DEFAULT_HEIGHT), subtitle, "#50606d", width - 2 * margin_x, scaled(34, height, DEFAULT_HEIGHT))

    status_bbox = [margin_x, scaled(314, height, DEFAULT_HEIGHT), width - margin_x, scaled(378, height, DEFAULT_HEIGHT)]
    draw_round_rect(draw, status_bbox, scaled(26, width, DEFAULT_WIDTH), fill=soft, outline="#c7d2de")
    draw_left_text(
        draw,
        status_bbox[0] + scaled(28, width, DEFAULT_WIDTH),
        status_bbox[1] + scaled(14, height, DEFAULT_HEIGHT),
        f"Synthetic screen {screen['screen_id']}",
        accent,
        status_bbox[2] - status_bbox[0] - scaled(56, width, DEFAULT_WIDTH),
        scaled(28, height, DEFAULT_HEIGHT),
        bold=True,
    )

    elements = screen["elements"]
    for index, element in enumerate(elements):
        bbox = element["bbox"]
        is_primary = element["distractor_group"] == spec.distractor_group
        is_tab = element["role"] == "tab"
        fill = accent if element["is_target_candidate"] else ("#ffffff" if not is_tab else soft)
        outline = "#0f172a" if element["is_target_candidate"] else "#c8d1dc"
        text_fill = "#ffffff" if element["is_target_candidate"] else ink
        radius = scaled(30 if is_primary else 22, width, DEFAULT_WIDTH)
        draw_round_rect(draw, bbox, radius=radius, fill=fill, outline=outline, width=scaled(3 if is_primary else 2, width, DEFAULT_WIDTH))
        draw_centered_text(
            draw,
            bbox,
            element["label"],
            fill=text_fill,
            preferred_size=scaled(38 if is_primary else 30, height, DEFAULT_HEIGHT),
            bold=is_primary or element["is_target_candidate"],
        )

    lexicon = screen["visible_lexicon"]
    lexicon_top = scaled(1370, height, DEFAULT_HEIGHT)
    lexicon_bottom = min(height - scaled(240, height, DEFAULT_HEIGHT), scaled(1630, height, DEFAULT_HEIGHT))
    if lexicon_bottom > lexicon_top + scaled(100, height, DEFAULT_HEIGHT):
        lexicon_bbox = [margin_x, lexicon_top, width - margin_x, lexicon_bottom]
        draw_round_rect(draw, lexicon_bbox, scaled(24, width, DEFAULT_WIDTH), fill="#ffffff", outline="#c8d1dc", width=scaled(2, width, DEFAULT_WIDTH))
        draw_lexicon_chips(draw, lexicon_bbox, lexicon[:12], accent, ink, width, height)

    image_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(image_path)


def make_screen_record(
    domain: str,
    domain_index: int,
    screen_number: int,
    language_mode: str,
    seed: int,
    width: int,
    height: int,
    output_dir: Path,
) -> dict:
    screen_id = f"{domain}_{domain_index:03d}"
    elements = build_elements(domain, screen_id, language_mode, variant=domain_index - 1)
    boxes = layout_boxes(width, height, len(elements))
    records: list[dict] = []
    seen_ids: set[str] = set()
    for index, (element, bbox) in enumerate(zip(elements, boxes)):
        base_id = f"{slugify(element.label)}_{element.role}"
        element_id = base_id
        if element_id in seen_ids:
            element_id = f"{base_id}_{index + 1}"
        seen_ids.add(element_id)
        records.append(
            {
                "element_id": element_id,
                "label": element.label,
                "role": element.role,
                "language": element.language,
                "bbox": bbox,
                "is_target_candidate": element.group == DOMAIN_SPECS[domain].distractor_group and index < 2,
                "distractor_group": element.group,
            }
        )

    visible_lexicon = sorted({item["label"] for item in records}, key=str.casefold)
    target_candidate_ids = [item["element_id"] for item in records if item["is_target_candidate"]]
    image_path = output_dir / "images" / f"{screen_id}.png"

    return {
        "screen_id": screen_id,
        "domain": domain,
        "image_path": image_path.as_posix(),
        "width": width,
        "height": height,
        "visible_lexicon": visible_lexicon,
        "target_candidate_ids": target_candidate_ids,
        "elements": records,
        "metadata": {
            "synthetic": True,
            "generator": "scripts/make_screens.py",
            "seed": seed,
            "domain_index": domain_index,
            "screen_number": screen_number,
            "language_mode": language_mode,
            "notes": "Synthetic benchmark UI only; no real app screenshots or private account data.",
        },
    }


def build_records(
    num_per_domain: int,
    seed: int,
    output_dir: Path,
    width: int,
    height: int,
) -> list[dict]:
    if num_per_domain < 1:
        raise ValueError("--num-per-domain must be at least 1")
    if width < 320 or height < 640:
        raise ValueError("image size is too small for readable mobile screens")

    rng = random.Random(seed)
    records: list[dict] = []
    global_screen_number = 1
    for domain in DOMAINS:
        domain_modes = list(LANGUAGE_CYCLE)
        rng.shuffle(domain_modes)
        for domain_index in range(1, num_per_domain + 1):
            language_mode = domain_modes[(domain_index - 1) % len(domain_modes)]
            records.append(
                make_screen_record(
                    domain=domain,
                    domain_index=domain_index,
                    screen_number=global_screen_number,
                    language_mode=language_mode,
                    seed=seed,
                    width=width,
                    height=height,
                    output_dir=output_dir,
                )
            )
            global_screen_number += 1
    return records


def prepare_output(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists() and overwrite:
        for path in (output_dir / "screens.jsonl", output_dir / "contact_sheet.png"):
            if path.exists():
                path.unlink()
        image_dir = output_dir / "images"
        if image_dir.exists():
            shutil.rmtree(image_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "images").mkdir(parents=True, exist_ok=True)


def write_jsonl(records: list[dict], output_dir: Path) -> Path:
    jsonl_path = output_dir / "screens.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return jsonl_path


def make_contact_sheet(records: list[dict], output_dir: Path) -> Path:
    thumbs: list[Image.Image] = []
    cell_w, cell_h = 270, 520
    label_h = 44
    for record in records:
        image = Image.open(record["image_path"]).convert("RGB")
        image.thumbnail((cell_w, cell_h - label_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (cell_w, cell_h), "#f8fafc")
        x = (cell_w - image.width) // 2
        canvas.paste(image, (x, 0))
        draw = ImageDraw.Draw(canvas)
        font = load_font(20, bold=True)
        draw.text((12, cell_h - label_h + 10), record["screen_id"], fill="#111827", font=font)
        thumbs.append(canvas)

    columns = min(5, max(1, len(thumbs)))
    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), "#e5e7eb")
    for index, thumb in enumerate(thumbs):
        x = (index % columns) * cell_w
        y = (index // columns) * cell_h
        sheet.paste(thumb, (x, y))

    sheet_path = output_dir / "contact_sheet.png"
    sheet.save(sheet_path)
    return sheet_path


def screen_label_mix(record: dict) -> str:
    languages = {element["language"] for element in record["elements"]}
    if languages == {"th"}:
        return "Thai-only"
    if languages == {"en"}:
        return "English-only"
    return "Mixed-label"


def report_table(rows: list[tuple[str, int]]) -> list[str]:
    lines = ["| Metric | Count |", "| --- | ---: |"]
    lines.extend(f"| {name} | {value} |" for name, value in rows)
    return lines


def make_screen_generation_report(
    records: list[dict],
    output_dir: Path,
) -> Path:
    report_path = output_dir / "SCREEN_GENERATION_REPORT.md"
    seed_values = {record["metadata"]["seed"] for record in records}
    seed = next(iter(seed_values)) if len(seed_values) == 1 else "multiple"
    screen_counts = Counter(record["domain"] for record in records)
    elements_by_domain: Counter[str] = Counter()
    target_candidates = 0
    group_instances = 0
    distinct_groups: set[str] = set()
    language_counts = Counter(screen_label_mix(record) for record in records)
    examples_by_group: dict[str, tuple[str, list[str]]] = {}

    for record in records:
        domain = record["domain"]
        elements_by_domain[domain] += len(record["elements"])
        target_candidates += len(record["target_candidate_ids"])
        labels_by_group: defaultdict[str, list[str]] = defaultdict(list)
        for element in record["elements"]:
            group = element["distractor_group"]
            labels_by_group[group].append(element["label"])
            distinct_groups.add(group)

        for group, labels in labels_by_group.items():
            if len(labels) >= 2:
                group_instances += 1
                examples_by_group.setdefault(group, (record["screen_id"], labels[:4]))

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "# Screen Generation Report",
        "",
        f"- Generation date: `{generated_at}`",
        f"- Seed: `{seed}`",
        f"- Number of screens: `{len(records)}`",
        f"- Number of target candidates: `{target_candidates}`",
        f"- Number of distractor groups: `{group_instances}` screen-level groups; `{len(distinct_groups)}` distinct group names",
        "",
        "## Screens Per Domain",
        "",
        *report_table([(domain, screen_counts[domain]) for domain in DOMAINS]),
        "",
        "## Elements Per Domain",
        "",
        *report_table([(domain, elements_by_domain[domain]) for domain in DOMAINS]),
        "",
        "## Label Mix",
        "",
        *report_table(
            [
                ("Thai-only screens", language_counts["Thai-only"]),
                ("English-only screens", language_counts["English-only"]),
                ("Mixed-label screens", language_counts["Mixed-label"]),
            ]
        ),
        "",
        "## Example Distractor Groups",
        "",
    ]

    for group in sorted(examples_by_group):
        screen_id, labels = examples_by_group[group]
        label_text = ", ".join(f"`{label}`" for label in labels)
        lines.append(f"- `{group}` in `{screen_id}`: {label_text}")

    lines.extend(
        [
            "",
            "## Known Limitations",
            "",
            "- Screens are synthetic templates, so they do not cover the full visual diversity of real mobile apps.",
            "- Labels are curated mock labels and do not model all Thai regional wording, slang, or speech-register variants.",
            "- Layouts use fixed mobile-style regions; overlapping, scrolling, modal, and gesture-heavy interfaces are out of scope.",
            "- Icons are represented mainly through text/button affordances, so icon-only grounding is not yet stressed.",
            "- TTS, ASR, correction, and grounding stages are not exercised by this screen-generation report.",
            "",
            "## Validation",
            "",
            "- Command: `python scripts/validate_screens.py --screens-jsonl data/screens/screens.jsonl --image-root .`",
            "- Result: `pending`",
            "",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def generate_screens(
    num_per_domain: int,
    seed: int,
    output_dir: Path,
    image_width: int,
    image_height: int,
    overwrite: bool,
    report: bool = False,
) -> list[dict]:
    prepare_output(output_dir, overwrite=overwrite)
    records = build_records(num_per_domain, seed, output_dir, image_width, image_height)
    existing_images = list((output_dir / "images").glob("*.png"))
    if existing_images and not overwrite:
        raise FileExistsError(f"{output_dir / 'images'} already contains PNGs; pass --overwrite to replace them")

    for record in records:
        render_screen(record, record["metadata"]["language_mode"], Path(record["image_path"]))
    write_jsonl(records, output_dir)
    make_contact_sheet(records, output_dir)
    if report:
        make_screen_generation_report(records, output_dir)
    return records


def main() -> int:
    args = parse_args()
    try:
        records = generate_screens(
            num_per_domain=args.num_per_domain,
            seed=args.seed,
            output_dir=args.output_dir,
            image_width=args.image_width,
            image_height=args.image_height,
            overwrite=args.overwrite,
            report=args.report,
        )
    except (FileExistsError, OSError, ValueError) as exc:
        print(f"Screen generation failed: {exc}")
        return 1
    element_count = sum(len(record["elements"]) for record in records)
    print(
        f"Generated {len(records)} screens, {element_count} elements, "
        f"metadata at {args.output_dir / 'screens.jsonl'}"
    )
    print(f"Contact sheet: {args.output_dir / 'contact_sheet.png'}")
    if args.report:
        print(f"Report: {args.output_dir / 'SCREEN_GENERATION_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
