"""Generate deterministic ThaiVoice-GUIBench utterances."""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


TIERS = ("T1_verbatim", "T2_paraphrase", "T3_intent", "T4_visual_positional")
LANGUAGE_CLASSES = ("pure_thai", "code_switched", "mostly_english")
DEFAULT_INTENTS = Path("data/intents/intents.jsonl")
DEFAULT_MAPPINGS = Path("data/intents/intent_screen_targets.jsonl")
DEFAULT_SCREENS = Path("data/screens/screens.jsonl")
DEFAULT_OUTPUT = Path("data/utterances/utterances.jsonl")

DOMAIN_PHRASES = {
    "mock_finance": "หน้าเงินจำลอง",
    "shopping": "หน้าซื้อของ",
    "settings": "หน้าตั้งค่า",
    "messaging": "หน้าแชต",
}

ROLE_WORDS = {
    "button": "ปุ่ม",
    "list_item": "รายการ",
    "tab": "แท็บ",
    "text_field": "ช่อง",
    "switch": "สวิตช์",
}

POLITE_ENDINGS = ("ให้หน่อย", "หน่อยได้ไหม", "ให้หน่อย")
GENDERED_PARTICLES = ("ครับ", "ค่ะ", "คะ")

# Only obvious copied labels/loanword spellings live here. Do not add general
# semantic Thai words such as โอนเงิน for Transfer; those are valid T2/T3 clues.
LABEL_ALIASES = {
    "transfer": ("ทรานส์เฟอร์", "ทรานเฟอร์"),
    "top up": ("ท็อปอัป", "ท็อปอัพ"),
    "withdraw": ("วิดดรอว์",),
    "history": ("ฮิสทอรี",),
    "pay bill": ("เพย์บิล",),
    "scan": ("สแกน",),
    "accounts": ("แอคเคานต์",),
    "search": ("เสิร์ช",),
    "sort": ("ซอร์ต",),
    "filter": ("ฟิลเตอร์",),
    "promotion": ("โปรโมชั่น",),
    "cart": ("คาร์ต",),
    "add cart": ("แอดคาร์ต",),
    "buy now": ("บาย นาว", "บายนาว"),
    "notifications": ("โนติฟิเคชัน", "โนติฟิเคชั่น"),
    "settings": ("เซตติง", "เซ็ตติ้ง"),
    "privacy": ("ไพรเวซี",),
    "security": ("ซีเคียวริตี้",),
    "about": ("อะเบาต์",),
    "send": ("เซนด์",),
    "mute": ("มิวต์",),
    "profile": ("โพรไฟล์",),
    "โปรโมชัน": ("โปรโมชั่น",),
}

T2_TEMPLATES = {
    "send_money": ("ช่วยโอนเงินให้คนนี้หน่อย", "ส่งเงินไปให้ผู้รับคนนี้ให้หน่อย"),
    "top_up_mobile": ("เพิ่มยอดมือถือให้หน่อย", "ช่วยเพิ่มเงินโทรศัพท์ให้หน่อย"),
    "check_transaction_history": ("เปิดรายการย้อนหลังให้หน่อย", "ดูรายการเงินก่อนหน้านี้ให้หน่อย"),
    "view_monthly_statement": ("เปิดสรุปรายเดือนให้หน่อย", "ขอดูรายการของเดือนนี้หน่อย"),
    "open_wallet_balance": ("พาไปดูยอดในกระเป๋าหน่อย", "เช็กยอดคงเหลือให้หน่อย"),
    "pay_bill": ("ช่วยชำระบิลจำลองให้หน่อย", "เปิดส่วนชำระค่าใช้จ่ายให้หน่อย"),
    "scan_qr_payment": ("เปิดกล้องคิวอาร์สำหรับจ่ายเงินให้หน่อย", "จะจ่ายด้วยคิวอาร์ ช่วยเปิดกล้องให้หน่อย"),
    "manage_saved_recipient": ("เปิดรายชื่อผู้รับที่บันทึกไว้ให้หน่อย", "จัดการคนรับเงินที่เคยบันทึกไว้ให้หน่อย"),
    "search_product": ("หาสินค้าที่ต้องการให้หน่อย", "ช่วยหาของที่จะซื้อให้หน่อย"),
    "sort_by_cheapest": ("จัดสินค้าให้ตัวเลือกประหยัดขึ้นก่อนหน่อย", "เรียงของให้ราคาต่ำมาก่อนให้หน่อย"),
    "open_cart": ("เปิดตะกร้าสินค้าให้หน่อย", "พาไปดูของที่เลือกไว้ในตะกร้าหน่อย"),
    "apply_filter": ("จำกัดรายการสินค้าตามเงื่อนไขให้หน่อย", "คัดของให้ตรงเงื่อนไขหน่อย"),
    "view_promotion": ("ดูข้อเสนอส่วนลดให้หน่อย", "เปิดดีลลดราคาตอนนี้ให้หน่อย"),
    "add_item_to_cart": ("เอาสินค้าที่เลือกใส่ตะกร้าให้หน่อย", "เก็บของชิ้นนี้ไว้ในตะกร้าให้หน่อย"),
    "buy_now": ("เริ่มซื้อสินค้าที่เลือกทันทีให้หน่อย", "ดำเนินการซื้อของชิ้นนี้ตอนนี้เลย"),
    "view_order_history": ("ดูสถานะพัสดุหรือรายการสั่งซื้อให้หน่อย", "ตามดูของที่เคยสั่งไว้ให้หน่อย"),
    "change_language": ("สลับคำแสดงผลของแอปให้หน่อย", "ปรับคำในแอปให้เข้ากับที่อ่านถนัดหน่อย"),
    "turn_off_notifications": ("ปิดการเตือนของแอปให้หน่อย", "ไม่ให้แอปเด้งเตือน ช่วยจัดการให้หน่อย"),
    "open_profile": ("เปิดข้อมูลโปรไฟล์ของฉันให้หน่อย", "พาไปดูข้อมูลส่วนตัวในแอปหน่อย"),
    "open_privacy_settings": ("เปิดส่วนจัดการความเป็นส่วนตัวให้หน่อย", "พาไปหน้าควบคุมข้อมูลส่วนตัวหน่อย"),
    "change_password_mock": ("เปิดหน้าจำลองแก้รหัสผ่านให้หน่อย", "ไปส่วนจำลองสำหรับปรับรหัสให้หน่อย"),
    "toggle_dark_mode": ("สลับเป็นโหมดมืดให้หน่อย", "ปรับหน้าจอให้มืดลงหน่อย"),
    "manage_payment_methods_mock": ("เปิดวิธีชำระเงินจำลองให้หน่อย", "จัดการช่องทางจ่ายเงินแบบจำลองให้หน่อย"),
    "open_help_center": ("เปิดหน้าช่วยเหลือให้หน่อย", "พาไปส่วนคำแนะนำการใช้งานหน่อย"),
    "search_message_history": ("หาข้อความเก่าในแชตให้หน่อย", "ช่วยหาเรื่องที่เคยคุยไว้ให้หน่อย"),
    "mute_chat": ("ปิดเสียงห้องแชตนี้ให้หน่อย", "ไม่ให้ห้องนี้เตือนเสียง ช่วยจัดการหน่อย"),
    "compose_new_message": ("เริ่มเขียนข้อความหาใครสักคนให้หน่อย", "เปิดทางเริ่มคุยเรื่องใหม่ให้หน่อย"),
    "send_message": ("ส่งข้อความที่พิมพ์ไว้ให้หน่อย", "เอาข้อความนี้ออกไปให้หน่อย"),
    "open_contact_profile": ("เปิดข้อมูลผู้ติดต่อคนนี้ให้หน่อย", "ดูรายละเอียดของคนที่คุยด้วยให้หน่อย"),
    "archive_chat": ("ย้ายแชตนี้ออกจากหน้าหลักให้หน่อย", "ซ่อนบทสนทนานี้ไว้ดูทีหลังให้หน่อย"),
}

T3_TEMPLATES = {
    "send_money": ("อยากส่งเงินให้คนนี้ ต้องกดตรงไหน", "จะให้เงินไปถึงผู้รับคนนี้ ต้องเลือกตรงไหน"),
    "top_up_mobile": ("มือถือเงินใกล้หมด ต้องไปตรงไหน", "อยากเพิ่มยอดโทรศัพท์ ต้องแตะตรงไหน"),
    "check_transaction_history": ("อยากดูว่าก่อนหน้านี้มีรายการอะไรบ้าง ต้องกดตรงไหน", "จะย้อนดูรายการเก่า ๆ ต้องเลือกตรงไหน"),
    "view_monthly_statement": ("อยากเช็กรายการของเดือนนี้ ต้องกดตรงไหน", "จะดูสรุปการใช้เงินรายเดือน ต้องแตะตรงไหน"),
    "open_wallet_balance": ("อยากรู้ว่ายอดตอนนี้เหลือเท่าไร ต้องแตะตรงไหน", "จะดูเงินคงเหลือในกระเป๋า ต้องกดตรงไหน"),
    "pay_bill": ("มีบิลจำลองที่ต้องจัดการ ต้องกดตรงไหน", "อยากชำระค่าใช้จ่ายในหน้าจำลอง ต้องแตะตรงไหน"),
    "scan_qr_payment": ("จะจ่ายด้วยคิวอาร์ ต้องกดตรงไหน", "อยากใช้กล้องอ่านคิวอาร์เพื่อจ่าย ต้องเลือกตรงไหน"),
    "manage_saved_recipient": ("อยากแก้คนรับเงินที่เคยบันทึกไว้ ต้องไปตรงไหน", "จะดูรายชื่อผู้รับเดิม ต้องแตะตรงไหน"),
    "search_product": ("อยากเจอของที่ต้องซื้อ ต้องกดตรงไหน", "จะหาของในร้านนี้ ต้องแตะตรงไหน"),
    "sort_by_cheapest": ("อยากเห็นของที่ราคาต่ำก่อน ต้องแตะตรงไหน", "จะเลือกดูสินค้าที่คุ้มที่สุดก่อน ต้องกดตรงไหน"),
    "open_cart": ("อยากดูของที่เลือกไว้แล้ว ต้องกดตรงไหน", "จะกลับไปดูของในตะกร้า ต้องแตะตรงไหน"),
    "apply_filter": ("อยากคัดของให้ตรงความต้องการ ต้องกดตรงไหน", "จะลดรายการให้เหลือแบบที่อยากได้ ต้องแตะตรงไหน"),
    "view_promotion": ("อยากรู้ว่ามีดีลอะไรตอนนี้ ต้องแตะตรงไหน", "จะดูของลดราคาช่วงนี้ ต้องกดตรงไหน"),
    "add_item_to_cart": ("อยากเก็บของชิ้นนี้ไว้ซื้อทีหลัง ต้องกดตรงไหน", "จะเอาของนี้ใส่ไว้ก่อน ต้องแตะตรงไหน"),
    "buy_now": ("อยากดำเนินการกับของชิ้นนี้ตอนนี้ ต้องกดตรงไหน", "จะซื้อของที่เลือกไว้เลย ต้องแตะตรงไหน"),
    "view_order_history": ("อยากรู้ของที่สั่งไว้ไปถึงไหนแล้ว ต้องแตะตรงไหน", "จะดูรายการที่เคยสั่ง ต้องกดตรงไหน"),
    "change_language": ("อยากให้แอปแสดงคำในแบบที่อ่านถนัด ต้องกดตรงไหน", "จะปรับคำบนแอปให้เข้าใจง่ายขึ้น ต้องแตะตรงไหน"),
    "turn_off_notifications": ("ไม่อยากให้แอปเด้งเตือน ต้องแตะตรงไหน", "ถ้าไม่อยากถูกรบกวนจากแอป ต้องกดตรงไหน"),
    "open_profile": ("อยากดูข้อมูลส่วนตัวในแอป ต้องกดตรงไหน", "จะเข้าไปดูรายละเอียดของตัวเอง ต้องแตะตรงไหน"),
    "open_privacy_settings": ("อยากควบคุมข้อมูลส่วนตัว ต้องแตะตรงไหน", "จะจัดการสิทธิ์และข้อมูลของเรา ต้องกดตรงไหน"),
    "change_password_mock": ("อยากเปลี่ยนรหัสในแบบจำลอง ต้องกดตรงไหน", "จะเข้าไปส่วนรหัสผ่านจำลอง ต้องแตะตรงไหน"),
    "toggle_dark_mode": ("อยากให้หน้าจอดูมืดลงตอนใช้งาน ต้องกดตรงไหน", "จะเปลี่ยนหน้าตาให้สบายตาตอนกลางคืน ต้องแตะตรงไหน"),
    "manage_payment_methods_mock": ("อยากจัดการช่องทางจ่ายเงินแบบจำลอง ต้องแตะตรงไหน", "จะดูวิธีจ่ายเงินที่ตั้งไว้ในหน้าจำลอง ต้องกดตรงไหน"),
    "open_help_center": ("มีเรื่องไม่เข้าใจ อยากหาคำแนะนำต้องกดตรงไหน", "ถ้าต้องการความช่วยเหลือในแอป ต้องแตะตรงไหน"),
    "search_message_history": ("อยากย้อนดูว่าคุยอะไรกันไว้ ต้องกดตรงไหน", "จะหาเรื่องที่เคยคุยกัน ต้องแตะตรงไหน"),
    "mute_chat": ("ไม่อยากได้เสียงเตือนจากห้องนี้ ต้องแตะตรงไหน", "ถ้าห้องนี้รบกวนเกินไป ต้องกดตรงไหน"),
    "compose_new_message": ("อยากเริ่มคุยเรื่องใหม่ ต้องกดตรงไหน", "จะเขียนไปหาคนใหม่ ต้องแตะตรงไหน"),
    "send_message": ("พิมพ์เสร็จแล้ว อยากให้ข้อความออกไป ต้องแตะตรงไหน", "จะให้ข้อความนี้ถึงอีกฝ่าย ต้องกดตรงไหน"),
    "open_contact_profile": ("อยากดูรายละเอียดของคนที่คุยด้วย ต้องกดตรงไหน", "จะเปิดข้อมูลของผู้ติดต่อคนนี้ ต้องแตะตรงไหน"),
    "archive_chat": ("อยากซ่อนบทสนทนานี้ไว้ทีหลัง ต้องแตะตรงไหน", "จะเอาห้องนี้ออกจากรายการหลัก ต้องกดตรงไหน"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intents", type=Path, default=DEFAULT_INTENTS)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS)
    parser.add_argument("--screens", type=Path, default=DEFAULT_SCREENS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--num-per-tier", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def screen_element_index(screens: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        screen["screen_id"]: {element["element_id"]: element for element in screen["elements"]}
        for screen in screens
    }


def screen_index(screens: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {screen["screen_id"]: screen for screen in screens}


def has_thai(text: str) -> bool:
    return any("\u0e00" <= char <= "\u0e7f" for char in text)


def has_ascii_word(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def loanword_spans(text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9]*(?:[ -][A-Za-z0-9]+)*", text):
        spans.append({"text": match.group(0), "start": match.start(), "end": match.end()})
    return spans


def classify_language(text: str) -> str:
    thai = has_thai(text)
    ascii_word = has_ascii_word(text)
    if ascii_word and not thai:
        return "mostly_english"
    if ascii_word and thai:
        return "code_switched"
    return "pure_thai"


def neutralize_polite_particles(text: str) -> str:
    for particle in GENDERED_PARTICLES:
        text = text.replace(particle, "")
    return re.sub(r"\s+", " ", text).strip()


def leakage_terms(label: str) -> list[str]:
    terms = [label.strip()]
    lowered = label.strip().lower()
    terms.extend(LABEL_ALIASES.get(lowered, ()))
    terms.extend(LABEL_ALIASES.get(label.strip(), ()))
    return [term for term in dict.fromkeys(terms) if term]


def contains_label_leak(text: str, label: str) -> tuple[bool, str | None]:
    text_lower = text.lower()
    for term in leakage_terms(label):
        if term.lower() in text_lower:
            return True, term
    return False, None


def choose_template(templates: tuple[str, ...], mapping_index: int, variant_index: int, rng: random.Random) -> str:
    # Deterministic but seed-sensitive ordering for num_per_tier > 1.
    offset = rng.randrange(len(templates)) if templates else 0
    return templates[(mapping_index + variant_index + offset) % len(templates)]


def choose_nonleaking_template(
    templates: tuple[str, ...],
    mapping_index: int,
    variant_index: int,
    rng: random.Random,
    target_label: str,
) -> str:
    # Preserve the original deterministic first choice when it is valid, but
    # fall forward for screens whose visible label matches an intent synonym.
    offset = rng.randrange(len(templates)) if templates else 0
    for step in range(len(templates)):
        text = templates[(mapping_index + variant_index + offset + step) % len(templates)]
        leaked, _ = contains_label_leak(text, target_label)
        if not leaked:
            return text
    raise ValueError(f"all templates leak target label or alias for label {target_label!r}")


def unique_text_variant(text: str, seen_text: set[str]) -> str:
    variants = (
        f"ในหน้านี้{text}",
        f"ตรงหน้านี้{text}",
        f"บนหน้าจอนี้{text}",
        f"{text}ในหน้านี้",
        f"{text}ตรงนี้",
    )
    for variant in variants:
        if variant not in seen_text:
            return variant
    raise ValueError(f"could not create unique text_gold variant for {text!r}")


def t1_text(target_label: str, intent_id: str, domain: str, mapping_index: int, variant_index: int) -> str:
    context = {
        "send_money": "ส่งเงิน",
        "top_up_mobile": "เติมยอดมือถือ",
        "check_transaction_history": "ดูรายการเก่า",
        "view_monthly_statement": "ดูสรุปรายเดือน",
        "open_wallet_balance": "ดูยอดเงิน",
        "pay_bill": "ชำระบิลจำลอง",
        "scan_qr_payment": "สแกนคิวอาร์",
        "manage_saved_recipient": "ดูผู้รับที่บันทึกไว้",
        "search_product": "หาสินค้า",
        "sort_by_cheapest": "จัดราคาสินค้า",
        "open_cart": "ดูตะกร้า",
        "apply_filter": "คัดสินค้า",
        "view_promotion": "ดูส่วนลด",
        "add_item_to_cart": "เก็บสินค้า",
        "buy_now": "ซื้อของ",
        "view_order_history": "ดูคำสั่งซื้อ",
        "change_language": "ปรับคำแสดงผล",
        "turn_off_notifications": "จัดการการเตือน",
        "open_profile": "ดูข้อมูลส่วนตัว",
        "open_privacy_settings": "จัดการข้อมูลส่วนตัว",
        "change_password_mock": "ไปส่วนรหัสจำลอง",
        "toggle_dark_mode": "ปรับหน้าจอมืด",
        "manage_payment_methods_mock": "จัดการวิธีจ่ายจำลอง",
        "open_help_center": "หาคำแนะนำ",
        "search_message_history": "หาข้อความเก่า",
        "mute_chat": "ลดการรบกวน",
        "compose_new_message": "เริ่มคุยใหม่",
        "send_message": "ส่งข้อความ",
        "open_contact_profile": "ดูผู้ติดต่อ",
        "archive_chat": "ซ่อนบทสนทนา",
    }[intent_id]
    domain_phrase = DOMAIN_PHRASES[domain]
    templates = (
        "กดปุ่ม {label} ใน{domain_phrase}เพื่อ{context}{ending}",
        "ช่วยแตะ {label} สำหรับ{context}{ending}",
        "เลือก {label} บน{domain_phrase}เพื่อ{context}{ending}",
        "กดตรง {label} เพื่อ{context}{ending}",
    )
    template = templates[(mapping_index + variant_index) % len(templates)]
    ending = POLITE_ENDINGS[(mapping_index + variant_index) % len(POLITE_ENDINGS)]
    return template.format(label=target_label, domain_phrase=domain_phrase, context=context, ending=ending)


def position_phrase(bbox: list[int], screen_width: int, screen_height: int) -> str:
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    horizontal = "ซ้าย" if cx < screen_width * 0.38 else "ขวา" if cx > screen_width * 0.62 else "ตรงกลาง"
    vertical = "ด้านบน" if cy < screen_height * 0.38 else "ด้านล่าง" if cy > screen_height * 0.70 else "กลางหน้าจอ"
    if vertical == "ด้านบน" and horizontal == "ขวา":
        return "มุมขวาบน"
    if vertical == "ด้านบน" and horizontal == "ซ้าย":
        return "มุมซ้ายบน"
    if vertical == "ด้านล่าง" and horizontal == "ขวา":
        return "มุมขวาล่าง"
    if vertical == "ด้านล่าง" and horizontal == "ซ้าย":
        return "มุมซ้ายล่าง"
    if horizontal == "ตรงกลาง":
        return vertical
    return f"{vertical}{horizontal}"


def t4_text(element: dict[str, Any], screen: dict[str, Any], domain: str, mapping_index: int, variant_index: int) -> str:
    role = ROLE_WORDS.get(element.get("role", "button"), "ส่วน")
    position = position_phrase(element["bbox"], screen["width"], screen["height"])
    domain_phrase = DOMAIN_PHRASES[domain]
    # Many targets share similar geometry across synthetic screens. Use a broad
    # set of natural openers so visual utterances remain unique without labels.
    openers = (
        "ช่วยกด",
        "รบกวนแตะ",
        "ขอเลือก",
        "ลองกด",
        "ช่วยแตะ",
        "กดตรง",
        "แตะตรง",
        "เลือกตรง",
        "ช่วยจิ้ม",
        "ขอแตะ",
        "กดที่",
        "แตะที่",
        "เลือกที่",
        "รบกวนกด",
        "ช่วยเลือก",
        "ขอจิ้ม",
        "กดบริเวณ",
        "แตะบริเวณ",
        "เลือกบริเวณ",
        "รบกวนเลือก",
        "ช่วยกดตรง",
        "ช่วยแตะตรง",
        "ขอกดตรง",
        "ขอแตะตรง",
        "กดอันที่เป็น",
        "แตะอันที่เป็น",
        "เลือกอันที่เป็น",
        "ช่วยกดส่วนที่เป็น",
        "รบกวนแตะส่วนที่เป็น",
        "ขอเลือกส่วนที่เป็น",
        "กดส่วน",
        "แตะส่วน",
    )
    closers = ("ให้หน่อย", "หน่อยได้ไหม", "ให้หน่อย")
    opener = openers[(mapping_index + variant_index) % len(openers)]
    closer = closers[(mapping_index + variant_index) % len(closers)]
    return f"{opener}{role}{position}ใน{domain_phrase}{closer}"


def make_utterance(
    mapping: dict[str, Any],
    intent: dict[str, Any],
    screen: dict[str, Any],
    element: dict[str, Any],
    tier: str,
    mapping_index: int,
    variant_index: int,
    rng: random.Random,
) -> dict[str, Any]:
    target_label = element["label"]
    if tier == "T1_verbatim":
        text = t1_text(target_label, intent["intent_id"], intent["domain"], mapping_index, variant_index)
        notes = "T1 may include the visible target label."
    elif tier == "T2_paraphrase":
        text = choose_nonleaking_template(
            T2_TEMPLATES[intent["intent_id"]], mapping_index, variant_index, rng, target_label
        )
        notes = "Generated from curated intent paraphrase without target label access."
    elif tier == "T3_intent":
        text = choose_nonleaking_template(
            T3_TEMPLATES[intent["intent_id"]], mapping_index, variant_index, rng, target_label
        )
        notes = "Generated from goal-style intent template without target label access."
    elif tier == "T4_visual_positional":
        text = t4_text(element, screen, intent["domain"], mapping_index, variant_index)
        notes = "Generated from bbox, role, and domain-level context only."
    else:
        raise ValueError(f"unsupported tier: {tier}")

    text = neutralize_polite_particles(text)

    if tier != "T1_verbatim":
        leaked, term = contains_label_leak(text, target_label)
        if leaked:
            raise ValueError(
                f"{mapping['mapping_id']} {tier} leaked target label or alias {term!r} in {text!r}"
            )

    tier_slug = tier.lower()
    return {
        "utterance_id": f"{mapping['mapping_id']}_{tier_slug}_{variant_index + 1:02d}",
        "mapping_id": mapping["mapping_id"],
        "intent_id": mapping["intent_id"],
        "screen_id": mapping["screen_id"],
        "target_element_id": mapping["target_element_id"],
        "tier": tier,
        "text_gold": text,
        "language_class": classify_language(text),
        "loanword_spans": loanword_spans(text),
        "generation_notes": notes,
    }


def duplicate_values(records: list[dict[str, Any]], field: str) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for record in records:
        value = record.get(field)
        if not isinstance(value, str):
            continue
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def load_sources(
    intents_path: Path,
    mappings_path: Path,
    screens_path: Path,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    intents = {record["intent_id"]: record for record in load_jsonl(intents_path)}
    mappings = load_jsonl(mappings_path)
    screens = screen_index(load_jsonl(screens_path))
    return intents, mappings, screens


def build_candidate_utterances(
    intents: dict[str, dict[str, Any]],
    mappings: list[dict[str, Any]],
    screens: dict[str, dict[str, Any]],
    num_per_tier: int,
    seed: int,
) -> list[dict[str, Any]]:
    elements_by_screen = screen_element_index(list(screens.values()))
    rng = random.Random(seed)

    utterances: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    for mapping_index, mapping in enumerate(mappings):
        intent = intents[mapping["intent_id"]]
        screen = screens[mapping["screen_id"]]
        element = elements_by_screen[mapping["screen_id"]][mapping["target_element_id"]]
        for tier in TIERS:
            for variant_index in range(num_per_tier):
                utterance = make_utterance(mapping, intent, screen, element, tier, mapping_index, variant_index, rng)
                if utterance["text_gold"] in seen_text:
                    utterance["text_gold"] = unique_text_variant(utterance["text_gold"], seen_text)
                    utterance["language_class"] = classify_language(utterance["text_gold"])
                    utterance["loanword_spans"] = loanword_spans(utterance["text_gold"])
                seen_text.add(utterance["text_gold"])
                utterances.append(utterance)

    duplicates = duplicate_values(utterances, "text_gold")
    if duplicates:
        raise ValueError(f"duplicate text_gold values generated: {duplicates[:3]}")
    return utterances


def generate_utterances(
    intents_path: Path,
    mappings_path: Path,
    screens_path: Path,
    output_path: Path,
    num_per_tier: int,
    seed: int,
    overwrite: bool,
) -> list[dict[str, Any]]:
    if num_per_tier < 1:
        raise ValueError("--num-per-tier must be at least 1")
    if output_path.exists() and output_path.stat().st_size > 0 and not overwrite:
        raise FileExistsError(f"{output_path} already exists; pass --overwrite to replace it")

    intents, mappings, screens = load_sources(intents_path, mappings_path, screens_path)
    candidates = build_candidate_utterances(intents, mappings, screens, num_per_tier, seed)

    write_jsonl(candidates, output_path)
    write_report(candidates, intents, mappings, screens, output_path.parent, seed)
    return candidates


def write_report(
    utterances: list[dict[str, Any]],
    intents: dict[str, dict[str, Any]],
    mappings: list[dict[str, Any]],
    screens: dict[str, dict[str, Any]],
    output_dir: Path,
    seed: int,
) -> Path:
    report_path = output_dir / "UTTERANCE_GENERATION_REPORT.md"
    tier_counts = Counter(record["tier"] for record in utterances)
    mapping_by_id = {mapping["mapping_id"]: mapping for mapping in mappings}
    domain_counts = Counter(
        intents[mapping_by_id[record["mapping_id"]]["intent_id"]]["domain"]
        for record in utterances
    )
    language_counts = Counter(record["language_class"] for record in utterances)
    examples = {}
    for tier in TIERS:
        examples[tier] = next(record["text_gold"] for record in utterances if record["tier"] == tier)

    lines = [
        "# Utterance Generation Report",
        "",
        f"- Generation date: `{datetime.now().astimezone().isoformat(timespec='seconds')}`",
        f"- Seed: `{seed}`",
        f"- Number of utterances: `{len(utterances)}`",
        f"- Number of mappings: `{len(mappings)}`",
    ]
    lines.extend(
        [
        "",
        "## Number Per Tier",
        "",
        "| Tier | Count |",
        "| --- | ---: |",
        ]
    )
    lines.extend(f"| {tier} | {tier_counts[tier]} |" for tier in TIERS)
    lines.extend(["", "## Number Per Domain", "", "| Domain | Count |", "| --- | ---: |"])
    for domain in ("mock_finance", "shopping", "settings", "messaging"):
        lines.append(f"| {domain} | {domain_counts[domain]} |")
    lines.extend(["", "## Language Class Distribution", "", "| Language class | Count |", "| --- | ---: |"])
    for language_class in LANGUAGE_CLASSES:
        lines.append(f"| {language_class} | {language_counts[language_class]} |")
    lines.extend(["", "## Examples By Tier", ""])
    for tier in TIERS:
        lines.append(f"- `{tier}`: {examples[tier]}")
    lines.extend(
        [
            "",
            "## Label-Leakage Warnings",
            "",
            "- None detected during generation self-check.",
            "",
            "## Validation And Tests",
            "",
            "- Validation result: pending",
            "- Test result: pending",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> int:
    args = parse_args()
    records = generate_utterances(
        intents_path=args.intents,
        mappings_path=args.mappings,
        screens_path=args.screens,
        output_path=args.output,
        num_per_tier=args.num_per_tier,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    print(f"Generated {len(records)} utterances at {args.output}")
    print(f"Report: {args.output.parent / 'UTTERANCE_GENERATION_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
