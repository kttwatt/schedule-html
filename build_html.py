#!/usr/bin/env python3
"""Generate index.html (ตารางเรียน) from schedule.md (authoritative) + schedule.json (course meta).

schedule.md is the hand-reconciled source of truth: it already reflects cancellations
("เลื่อน", marked with ❌) and sessions moved to later dates. schedule.json is only used
for course header metadata (code/name/program/period).
"""
import json
import re
import html
from datetime import datetime, timedelta
from urllib.parse import quote

# Course-materials doc-chip feature (📄 filename links under each session).
# Parked for now, but parsing/mapping logic stays intact — flip to True to
# bring back doc-chip rendering + its CSS without touching anything else.
DOC_CHIPS = False

THAI_MONTHS = [
    "", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]

FORMAT_META = {
    "onsite":    {"label": "Onsite", "class": "fmt-onsite"},
    "hybrid":    {"label": "Hybrid", "class": "fmt-hybrid"},
    "selfstudy": {"label": "Self-study", "class": "fmt-selfstudy"},
    "exam":      {"label": "สอบ", "class": "fmt-exam"},
    "clinical":  {"label": "Clinical", "class": "fmt-clinical"},
    "sitevisit": {"label": "Site visit", "class": "fmt-sitevisit"},
}

LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
BOLD_RE = re.compile(r'\*\*([^*]+)\*\*')
URL_RE = re.compile(r'https?://\S+')
INLINE_RE = re.compile(f'(?:{LINK_RE.pattern})|(?:{BOLD_RE.pattern})|(?:{URL_RE.pattern})')

MATERIALS_REPO_RAW = "https://github.com/kttwatt/schedule-materials/raw/main"

# schedule.md's เอกสารเรียน column links point at old flat materials/ paths.
# The actual files now live in kttwatt/schedule-materials, reorganized into
# category subfolders. Map each old path -> new subfolder/filename.
MATERIALS_MAP = {
    "materials/2026-08-19-ethics-law-prangtip.pdf": "02-leadership/2026-08-19-ethics-law-prangtip.pdf",
    "materials/2026-08-20-leadership-autchariya.pdf": "02-leadership/2026-08-20-leadership-autchariya.pdf",
    "materials/2026-08-20-communication-autchariya.pdf": "02-leadership/2026-08-20-communication-autchariya.pdf",
    "materials/2026-08-21-psycho-social-assessment.pdf": "02-leadership/2026-08-21-psycho-social-assessment.pdf",
    "materials/Lecture_Workforce_August2026.pdf": "02-leadership/Lecture_Workforce_August2026.pdf",
    "materials/2026-08-21-health-economics-pichet.pdf": "01-orientation-policy/2026-08-21-health-economics-pichet.pdf",
    "materials/2026-08-21-health-financing-pichet.pdf": "01-orientation-policy/2026-08-21-health-financing-pichet.pdf",
    "materials/unit1-health-policy.pdf": "01-orientation-policy/unit1-health-policy.pdf",
    "materials/unit1-policy-slides.pdf": "01-orientation-policy/unit1-policy-slides.pdf",
    "materials/2026-08-24-unit3-perioperative-concepts.pdf": "03-perioperative/2026-08-24-unit3-perioperative-concepts.pdf",
    "materials/2026-08-26-ha-certification.pdf": "03-perioperative/2026-08-26-ha-certification.pdf",
    "materials/rubric-takehome-exam.docx": "05-assignments/rubric-takehome-exam.docx",
    "materials/Workshop_Workforce_August2026.docx": "05-assignments/Workshop_Workforce_August2026.docx",
    "materials/Workshop_Workforce_August2026.md": "05-assignments/Workshop_Workforce_August2026.md",
    "materials/กลุ่ม Policy+Workforce_เฉพาะทางสาขาการพยาบาลปริศัลยกรรม 55 ก1.md":
        "06-seminars/กลุ่ม Policy+Workforce_เฉพาะทางสาขาการพยาบาลปริศัลยกรรม 55 ก1.md",
}


def materials_link_href(old_path):
    """Map an old materials/... path (as written in schedule.md) to a raw
    GitHub URL in the private kttwatt/schedule-materials repo."""
    new_path = MATERIALS_MAP.get(old_path)
    if not new_path:
        return None
    return f"{MATERIALS_REPO_RAW}/{quote(new_path)}"


def render_materials(materials_text):
    """Render the เอกสารเรียน cell as small doc-link chips."""
    if not materials_text or materials_text == "-":
        return ""
    chips = []
    for label, path in LINK_RE.findall(materials_text):
        href = materials_link_href(path)
        if not href:
            continue
        chips.append(f'<a class="doc-chip" href="{esc(href)}" target="_blank" rel="noopener">📄 {esc(label)}</a>')
    if not chips:
        return ""
    return f'<span class="materials">{"".join(chips)}</span>'


def esc(s):
    return html.escape(s or "", quote=True)


def render_inline(text):
    """Minimal markdown -> HTML: [text](url), **bold**, bare URLs."""
    if not text:
        return ""
    out = []
    pos = 0
    for m in INLINE_RE.finditer(text):
        out.append(esc(text[pos:m.start()]))
        if m.group(1) is not None:
            out.append(f'<a href="{esc(m.group(2))}">{esc(m.group(1))}</a>')
        elif m.group(3) is not None:
            out.append(f'<strong>{esc(m.group(3))}</strong>')
        else:
            url = m.group(0)
            out.append(f'<a href="{esc(url)}">{esc(url)}</a>')
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def thai_date(iso_date):
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return iso_date or ""
    return f"{d.day} {THAI_MONTHS[d.month]} {d.year + 543}"


MONTH_TO_NUM = {m: i for i, m in enumerate(THAI_MONTHS) if m}
DATE_TEXT_RE = re.compile(r"(\d{1,2})\s+(\S+)\s+(\d{4})")


def parse_thai_date_text(date_text):
    """'จ. 17 ส.ค. 2569' -> '2026-08-17' (Buddhist year, Thai month abbrev)."""
    m = DATE_TEXT_RE.search(date_text or "")
    if not m:
        return None
    day, month_th, year_be = m.groups()
    month = MONTH_TO_NUM.get(month_th)
    if not month:
        return None
    try:
        d = datetime(int(year_be) - 543, month, int(day))
    except ValueError:
        return None
    return d.strftime("%Y-%m-%d")


def split_row(line):
    parts = line.strip().split("|")
    return [p.strip() for p in parts[1:-1]]


def is_separator_row(cells):
    return all(re.fullmatch(r"-+", c) for c in cells if c)


def parse_schedule_md(text):
    lines = text.splitlines()
    n = len(lines)
    i = 0

    # --- main schedule table ---
    while i < n and not lines[i].startswith("| วันที่"):
        i += 1
    i += 1  # header row
    i += 1  # separator row

    main_rows = []
    while i < n and not lines[i].startswith("## "):
        if lines[i].startswith("|"):
            main_rows.append(lines[i])
        i += 1

    sessions = []
    week_label = ""
    for line in main_rows:
        cells = split_row(line)
        if is_separator_row(cells):
            continue
        m = re.fullmatch(r"\*\*(.+)\*\*", cells[0])
        if m:
            week_label = m.group(1)
            continue
        if len(cells) < 6:
            continue
        date_text, time_text, unit, topic, lecturer, room = cells[:6]
        materials = cells[7] if len(cells) > 7 else ""
        if "ไม่มีข้อมูลในเอกสารต้นฉบับ" in topic:
            continue
        cancelled = topic.startswith("❌")
        topic = topic.lstrip("❌").strip()
        sessions.append({
            "week": week_label,
            "date_text": date_text,
            "time": time_text,
            "unit": unit,
            "topic": topic,
            "lecturer": lecturer,
            "room": room,
            "cancelled": cancelled,
            "materials": materials,
        })

    # --- homework table ---
    while i < n and "การบ้าน/งานส่ง" not in lines[i]:
        i += 1
    while i < n and not lines[i].startswith("| งาน"):
        i += 1
    i += 1  # header
    i += 1  # separator

    hw_rows = []
    while i < n and lines[i].startswith("|"):
        hw_rows.append(lines[i])
        i += 1

    homework = []
    for line in hw_rows:
        cells = split_row(line)
        if is_separator_row(cells) or len(cells) < 5:
            continue
        homework.append(cells)

    notes = []
    while i < n and not lines[i].startswith("## "):
        stripped = lines[i].strip()
        if stripped.startswith(">"):
            notes.append(stripped.lstrip(">").strip())
        i += 1

    return sessions, homework, notes


def detect_format(topic, room):
    t, r = topic, room
    rl = r.lower()
    tl = t.lower()
    if "สอบ" in t or "สอบ" in r:
        return "exam"
    if "hybrid" in rl:
        return "hybrid"
    if "self-study" in tl or "self-study" in rl:
        return "selfstudy"
    if "clinical practice" in rl or "clinical practice" in tl:
        return "clinical"
    if "site visit" in rl:
        return "sitevisit"
    return "onsite"


def pill_label(fmt, room):
    meta = FORMAT_META[fmt]
    if fmt in ("onsite", "clinical", "sitevisit") and room and room != "-":
        return room
    return meta["label"]


def group_by_day(sessions):
    days = []
    for s in sessions:
        if not days or days[-1]["date_text"] != s["date_text"]:
            days.append({
                "date_text": s["date_text"],
                "week": s["week"],
                "date_iso": parse_thai_date_text(s["date_text"]),
                "sessions": [],
            })
        days[-1]["sessions"].append(s)
    return days


THAI_WEEKDAYS = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]

# Official Thai public holidays that fall on non-class days in the term (17 ส.ค. – 4 ธ.ค. 69).
HOLIDAY_NAMES = {
    "2026-10-13": "วันนวมินทรมหาราช (คล้ายวันสวรรคต ร.9)",
    "2026-10-23": "วันปิยมหาราช",
}

def full_thai_date(iso):
    """'2026-08-29' -> 'วันเสาร์ 29 ส.ค. 2569'."""
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
    except (ValueError, TypeError):
        return iso or ""
    return f"{THAI_WEEKDAYS[d.weekday()]} {d.day} {THAI_MONTHS[d.month]} {d.year + 543}"


def with_weekends_holidays(days):
    """Fill in every calendar day between first and last session as a visible day block,
    marking days without sessions (weekends / holidays) as 'วันหยุด'."""
    real = [d for d in days if d.get("date_iso")]
    if len(real) < 2:
        return days
    by_iso = {}
    for d in real:
        # merge duplicate iso (shouldn't happen, but be safe): keep sessions combined
        if d["date_iso"] in by_iso:
            by_iso[d["date_iso"]]["sessions"].extend(d["sessions"])
        else:
            by_iso[d["date_iso"]] = d
    isos = sorted(by_iso.keys())
    start = datetime.strptime(isos[0], "%Y-%m-%d")
    end = datetime.strptime(isos[-1], "%Y-%m-%d")
    out = []
    cur = start
    while cur <= end:
        iso = cur.strftime("%Y-%m-%d")
        if iso in by_iso:
            out.append(by_iso[iso])
        else:
            out.append({
                "date_text": "",
                "week": "",
                "date_iso": iso,
                "sessions": [],
                "holiday": True,
            })
        cur += timedelta(days=1)
    return out


def render_session_row(s):
    fmt = detect_format(s["topic"], s["room"])
    classes = ["row"]
    if s["cancelled"]:
        classes.append("cancelled")

    time_html = f'<span class="time">{esc(s["time"])}</span>' if s["time"] and s["time"] != "-" else '<span class="time">–</span>'

    unit_html = ""
    if s["unit"] and s["unit"] != "-":
        unit_html = f'<span class="unit">{esc(s["unit"])}</span>'

    topic_html = f'<span class="topic">{unit_html}{esc(s["topic"])}</span>'

    who_html = f'<span class="who">{esc(s["lecturer"])}</span>' if s["lecturer"] and s["lecturer"] != "-" else ""

    if s["cancelled"]:
        pill_html = '<span class="pill fmt-cancelled">เลื่อน</span>'
    else:
        meta = FORMAT_META[fmt]
        pill_html = f'<span class="pill {meta["class"]}">{esc(pill_label(fmt, s["room"]))}</span>'

    materials_html = render_materials(s.get("materials")) if DOC_CHIPS else ""
    if materials_html:
        classes.append("has-materials")

    body_html = f'<div class="row-body"><div class="topic-line">{topic_html}{pill_html}</div>{who_html}{materials_html}</div>'
    row_main_html = f'<div class="row-main">{time_html}{body_html}</div>'

    return f'<div class="{" ".join(classes)}">{row_main_html}</div>'


def render_day(day, prev_week):
    week_html = ""
    if day["week"] and day["week"] != prev_week:
        week_html = f'<div class="week-div">{esc(day["week"])}</div>'
    if day.get("sessions"):
        rows_html = "\n".join(render_session_row(s) for s in day["sessions"])
    else:
        note = HOLIDAY_NAMES.get(day.get("date_iso")) or "วันหยุด"
        rows_html = f'<div class="holiday-row">— {esc(note)} —</div>'
    date_attr = f' data-date="{esc(day["date_iso"])}"' if day.get("date_iso") else ""
    head_text = day.get("date_text") or full_thai_date(day.get("date_iso")) or ""
    cls = ' class="day holiday"' if day.get("holiday") else ' class="day"'
    week_link_html = ""
    if day.get("sessions") and day.get("date_iso"):
        week_link_html = (
            f'<button type="button" class="day-week-link" data-date="{esc(day["date_iso"])}">'
            f"ดูรายสัปดาห์</button>"
        )
    return week_html + f"""<section{cls}{date_attr}>
  <div class="day-head"><span class="day-head-text">{esc(expand_day_abbrev(head_text))}</span>{week_link_html}</div>
  {rows_html}
</section>"""


DAY_FULL = {
    "จ.": "วันจันทร์", "อ.": "วันอังคาร", "พ.": "วันพุธ",
    "พฤ.": "วันพฤหัสบดี", "ศ.": "วันศุกร์", "ส.": "วันเสาร์",
    "อา.": "วันอาทิตย์",
}
DAY_ABBR_RE = re.compile(r"^(จ\.|อ\.|พ\.|พฤ\.|ศ\.|ส\.|อา\.)\s+")

def expand_day_abbrev(date_text):
    """'จ. 17 ส.ค. 2569' -> 'วันจันทร์ 17 ส.ค. 2569'."""
    m = DAY_ABBR_RE.match(date_text or "")
    if not m:
        return date_text or ""
    return DAY_FULL[m.group(1)] + " " + date_text[len(m.group(0)):]


TIME_SPAN_RE = re.compile(r"(\d{1,2})[.:](\d{2})\s*[–-]\s*(\d{1,2})[.:](\d{2})")

GRID_START_MIN = 8 * 60
GRID_END_MIN = 17 * 60
SLOT_MIN = 30
SLOT_COUNT = (GRID_END_MIN - GRID_START_MIN) // SLOT_MIN  # 18 half-hour slots, 08:00-17:00

GRID_WEEKDAY_ABBR = ["จ.", "อ.", "พ.", "พฤ.", "ศ."]  # Mon..Fri
GRID_WEEKDAY_CLASS = ["wg-mon", "wg-tue", "wg-wed", "wg-thu", "wg-fri"]


def parse_time_span(time_text):
    """'09.00–10.00' -> (540, 600) minutes since midnight; None if unparsable."""
    m = TIME_SPAN_RE.search(time_text or "")
    if not m:
        return None
    h1, m1, h2, m2 = m.groups()
    start = int(h1) * 60 + int(m1)
    end = int(h2) * 60 + int(m2)
    if end <= start:
        return None
    return start, end


def minutes_to_slot(mins):
    slot = round((mins - GRID_START_MIN) / SLOT_MIN)
    return max(0, min(SLOT_COUNT, slot))


def build_week_grids(sessions):
    """Group sessions by week label into per-weekday (Mon-Fri) buckets for the grid view."""
    order = []
    by_week = {}
    for s in sessions:
        wk = s.get("week")
        iso = parse_thai_date_text(s.get("date_text"))
        if not wk or not iso:
            continue
        span = parse_time_span(s.get("time"))
        if not span:
            continue
        by_week.setdefault(wk, [])
        if wk not in order:
            order.append(wk)
        by_week[wk].append((iso, span[0], span[1], s))

    grids = []
    for wk in order:
        entries = by_week[wk]
        d0 = datetime.strptime(entries[0][0], "%Y-%m-%d")
        monday = d0 - timedelta(days=d0.weekday())
        day_buckets = [[] for _ in range(5)]
        for iso, start, end, s in entries:
            d = datetime.strptime(iso, "%Y-%m-%d")
            idx = (d - monday).days
            if 0 <= idx < 5:
                day_buckets[idx].append((start, end, s))
        days = []
        for idx in range(5):
            day_date = monday + timedelta(days=idx)
            days.append({
                "idx": idx,
                "date_iso": day_date.strftime("%Y-%m-%d"),
                "day_num": day_date.day,
                "sessions": sorted(day_buckets[idx], key=lambda t: t[0]),
            })
        grids.append({"label": wk, "days": days})
    return grids


def assign_lanes(day_sessions):
    """Greedy interval packing: place (start,end,s) tuples into the fewest
    overlapping lanes. Returns (list of (lane, start_slot, end_slot, s), lane_count)."""
    lane_ends = []
    placed = []
    for start, end, s in day_sessions:
        start_slot = minutes_to_slot(start)
        end_slot = minutes_to_slot(end)
        if end_slot <= start_slot:
            continue
        lane_idx = None
        for li, lend in enumerate(lane_ends):
            if start_slot >= lend:
                lane_idx = li
                break
        if lane_idx is None:
            lane_idx = len(lane_ends)
            lane_ends.append(end_slot)
        else:
            lane_ends[lane_idx] = end_slot
        placed.append((lane_idx, start_slot, end_slot, s))
    return placed, max(len(lane_ends), 1)


def render_grid_session(start_slot, end_slot, row, s, weekday_class):
    classes = ["wg-session", weekday_class]
    if s["cancelled"]:
        classes.append("wg-cancelled")
    topic = s["topic"]
    lecturer = s["lecturer"] if s["lecturer"] and s["lecturer"] != "-" else ""
    room = s["room"] if s["room"] and s["room"] != "-" else ""
    unit = s["unit"] if s["unit"] and s["unit"] != "-" else ""
    time_text = s["time"] if s["time"] and s["time"] != "-" else ""
    fmt = detect_format(topic, s["room"])
    fmt_label = pill_label(fmt, s["room"])
    title = f"{topic} — {lecturer}" if lecturer else topic
    meta_html = ""
    if lecturer or room:
        room_html = f'<span class="wg-room">{esc(room)}</span>' if room else ""
        meta_html = f'<div class="wg-meta"><span class="wg-lect">{esc(lecturer)}</span>{room_html}</div>'
    style = f"grid-column:{start_slot + 2}/{end_slot + 2}; grid-row:{row}"
    data_attrs = (
        f'data-topic="{esc(topic)}" data-lecturer="{esc(lecturer)}" data-room="{esc(room)}" '
        f'data-time="{esc(time_text)}" data-unit="{esc(unit)}" data-fmt="{esc(fmt)}" '
        f'data-fmt-class="{esc(FORMAT_META[fmt]["class"])}" data-fmt-label="{esc(fmt_label)}" '
        f'data-cancelled="{"1" if s["cancelled"] else "0"}"'
    )
    return (f'<div class="{" ".join(classes)}" style="{style}" title="{esc(title)}" {data_attrs}>'
            f'<div class="wg-topic">{esc(topic)}</div>{meta_html}</div>')


def render_grid_free(start_slot, end_slot, row):
    if end_slot <= start_slot:
        return ""
    style = f"grid-column:{start_slot + 2}/{end_slot + 2}; grid-row:{row}"
    return f'<div class="wg-free" style="{style}"></div>'


def render_week_grid(week_label, days):
    row = 2  # row 1 = hour header
    body_parts = []
    for day in days:
        weekday_class = GRID_WEEKDAY_CLASS[day["idx"]]
        abbr = GRID_WEEKDAY_ABBR[day["idx"]]
        placed, lane_count = assign_lanes(day["sessions"])
        has_sessions = "1" if placed else "0"
        row_start = row
        for lane in range(lane_count):
            lane_items = sorted((p for p in placed if p[0] == lane), key=lambda p: p[1])
            cursor = 0
            for _, start_slot, end_slot, s in lane_items:
                if start_slot > cursor:
                    body_parts.append(render_grid_free(cursor, start_slot, row))
                body_parts.append(render_grid_session(start_slot, end_slot, row, s, weekday_class))
                cursor = max(cursor, end_slot)
            if cursor < SLOT_COUNT:
                body_parts.append(render_grid_free(cursor, SLOT_COUNT, row))
            row += 1
        body_parts.append(
            f'<div class="wg-daylabel {weekday_class}" data-date="{esc(day["date_iso"])}" '
            f'data-has-class="{has_sessions}" style="grid-column:1; grid-row:{row_start}/{row}">'
            f'{esc(abbr)} {day["day_num"]}</div>'
        )
    header_parts = ['<div class="wg-corner" style="grid-column:1; grid-row:1"></div>']
    for i in range(9):
        hour = 8 + i
        col = 2 + i * 2
        end_label = '<span class="wg-hour-end">17:00</span>' if i == 8 else ""
        header_parts.append(
            f'<div class="wg-hour" style="grid-column:{col}/{col + 2}; grid-row:1">'
            f'<span>{hour:02d}:00</span>{end_label}</div>'
        )
    grid_html = "".join(header_parts) + "".join(body_parts)
    return f"""<section class="week-grid">
  <h3 class="week-grid-title">{esc(week_label)}</h3>
  <div class="grid-scroll">
    <div class="wgrid">{grid_html}</div>
  </div>
</section>"""


def build_grid_view(sessions):
    grids = build_week_grids(sessions)
    return "\n".join(render_week_grid(g["label"], g["days"]) for g in grids)


def render_homework(homework, notes):
    if not homework:
        return ""
    header = ["งาน", "วิชา/หน่วย", "กำหนดส่ง", "คะแนน", "ลิงก์"]
    thead = "".join(f"<th>{esc(h)}</th>" for h in header)
    rows = []
    for cells in homework:
        tds = "".join(f"<td>{render_inline(c)}</td>" for c in cells)
        rows.append(f"<tr>{tds}</tr>")
    notes_html = ""
    if notes:
        items = "".join(f"<li>{render_inline(n)}</li>" for n in notes)
        notes_html = f'<ul class="hw-notes">{items}</ul>'
    return f"""
<section class="homework">
  <h2>การบ้าน/งานส่ง</h2>
  <div class="hw-table-wrap">
    <table>
      <thead><tr>{thead}</tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
  {notes_html}
</section>"""


CSS = """
:root {
  --bg: #f6f7f9;
  --card: #fff;
  --text: #1f2530;
  --muted: #6b7280;
  --border: #e5e9f0;
  --primary: #2563eb;
  --primary-light: #eaf1fe;
  --exam: #dc2626;
  --exam-light: #fdecec;
  --hybrid: #7c3aed;
  --hybrid-light: #f1ebfe;
  --selfstudy: #6b7280;
  --selfstudy-light: #eef0f3;
  --clinical: #059669;
  --clinical-light: #e6f7f1;
  --sitevisit: #d97706;
  --sitevisit-light: #fdf2e2;
  --today: #166534;
  --today-light: #dcfce7;
  --today-text: #14532d;
  --grid-mon: #fff3b0;
  --grid-mon-text: #7a5b00;
  --grid-tue: #ffd6ea;
  --grid-tue-text: #97295a;
  --grid-wed: #d5f5d0;
  --grid-wed-text: #1f6b2e;
  --grid-thu: #ffe0c2;
  --grid-thu-text: #9a4b00;
  --grid-fri: #cfeeff;
  --grid-fri-text: #0b5f80;
}
* { box-sizing: border-box; }
html { font-size: 18px; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Noto Sans Thai", "Sarabun", "TH Sarabun New", -apple-system, BlinkMacSystemFont,
    "Segoe UI", system-ui, sans-serif;
  line-height: 1.4;
}
.container { max-width: 760px; margin: 0 auto; padding: 14px 12px 48px; }

header.course-header {
  padding: 14px 2px 16px;
  border-bottom: 2px solid var(--primary);
  margin-bottom: 10px;
}
header.course-header .header-program { font-size: 1.6rem; font-weight: 700; color: var(--text); line-height: 1.35; }
header.course-header .period { font-size: 1.25rem; font-weight: 600; color: var(--text); margin-top: 6px; }

.legend {
  display: flex; flex-wrap: wrap; gap: 6px;
  margin-bottom: 14px; font-size: .85rem;
}

.week-div {
  font-size: .88rem; font-weight: 700; color: var(--primary);
  margin: 16px 0 4px; text-transform: uppercase; letter-spacing: .03em;
}
.week-div:first-child { margin-top: 0; }

.day { margin-bottom: 4px; }
.day.holiday .day-head {
  color: var(--muted);
  font-weight: 600;
  background: color-mix(in srgb, var(--card) 55%, transparent);
  border-style: dashed;
}
.holiday-row {
  padding: 8px 12px;
  font-size: .85rem;
  color: var(--muted);
  text-align: center;
  background: color-mix(in srgb, var(--card) 35%, transparent);
  border-radius: 6px;
  margin-top: 2px;
}
.day-head {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  font-size: .96rem; font-weight: 700;
  background: var(--card);
  border-radius: 6px;
  padding: 4px 8px;
  margin-top: 6px;
  position: sticky; top: 0;
  border: 1px solid var(--border);
}
.day-week-link {
  flex: 0 0 auto;
  font-family: inherit;
  font-size: .72rem;
  font-weight: 600;
  color: #fff;
  background: var(--primary);
  border: none;
  border-radius: 999px;
  padding: 4px 10px;
  cursor: pointer;
  white-space: nowrap;
}
.day-week-link:hover { opacity: .88; }

.day.today {
  border-left: 3px solid var(--today);
  background: var(--today-light);
  border-radius: 6px;
  padding: 2px 0 4px 6px;
  margin-left: -6px;
}
.day.today .day-head {
  background: var(--today-light);
  border-color: var(--today);
  color: var(--today-text);
  position: sticky; top: 0;
}
.today-badge {
  display: inline-block;
  margin-left: 6px;
  font-size: .76rem;
  font-weight: 700;
  color: #fff;
  background: var(--today);
  padding: 1px 7px;
  border-radius: 999px;
  vertical-align: middle;
}

.row {
  display: block;
  padding: 5px 8px;
  border-bottom: 1px solid var(--border);
  font-size: .96rem;
}
.row:last-child { border-bottom: none; }

.row-main {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.row .time {
  flex: 0 0 7.5em;
  flex-shrink: 0;
  font-weight: 600;
  color: var(--primary);
  font-variant-numeric: tabular-nums;
  font-size: .9rem;
  white-space: nowrap;
  min-width: 0;
}
.row .unit {
  font-size: .8rem;
  color: var(--muted);
  background: #eef2f7;
  border-radius: 4px;
  padding: 1px 4px;
  margin-right: 4px;
}
.row-body {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.topic-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.row .topic { flex: 1 1 auto; min-width: 0; }
.row .who { display: block; font-size: .88rem; color: var(--muted); min-width: 0; }
.row .materials {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}
.doc-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: .78rem;
  color: var(--primary);
  background: var(--primary-light);
  border: 1px solid var(--primary);
  border-radius: 999px;
  padding: 1px 8px;
  text-decoration: none;
  white-space: nowrap;
  line-height: 1.6;
}
.doc-chip:hover { text-decoration: underline; }
.row .pill {
  margin-left: auto;
  align-self: flex-start;
  flex: 0 0 auto;
  font-size: .8rem;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 999px;
  white-space: nowrap;
}

.row.cancelled { opacity: .65; }
.row.cancelled .topic { text-decoration: line-through; color: var(--muted); }
.row.cancelled .who { text-decoration: line-through; }

.fmt-onsite    { background: var(--primary-light); color: var(--primary); }
.fmt-hybrid    { background: var(--hybrid-light);   color: var(--hybrid); }
.fmt-selfstudy { background: var(--selfstudy-light);color: var(--selfstudy); }
.fmt-exam      { background: var(--exam-light);     color: var(--exam); }
.fmt-clinical  { background: var(--clinical-light); color: var(--clinical); }
.fmt-sitevisit { background: var(--sitevisit-light);color: var(--sitevisit); }
.fmt-cancelled { background: #f0f0f0; color: #9ca3af; }

.homework { margin-top: 26px; }
.homework h2 {
  font-size: 1.18rem; border-bottom: 2px solid var(--primary);
  padding-bottom: 6px; margin: 0 0 10px;
}
.hw-table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .92rem; background: var(--card); }
th, td { border: 1px solid var(--border); padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: var(--primary-light); color: var(--primary); font-size: .88rem; }
table a { color: var(--primary); }

.hw-notes { margin: 10px 0 0; padding-left: 18px; font-size: .88rem; color: var(--muted); }
.hw-notes li { margin-top: 4px; }

footer.page-footer {
  text-align: center; color: var(--muted); font-size: .85rem; margin-top: 24px;
}

@media (max-width: 620px) {
  html { font-size: 17px; }
  .row-main {
    flex-direction: column;
    align-items: stretch;
    gap: 3px;
  }
  .row .time {
    flex: 0 0 auto;
    font-size: .85rem;
    font-weight: 600;
  }
  .row .topic { flex: 1 1 auto; }
}

.fab-today {
  position: fixed;
  right: 16px;
  bottom: calc(16px + env(safe-area-inset-bottom, 0px));
  z-index: 40;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 46px;
  min-width: 46px;
  padding: 0 16px;
  border: none;
  border-radius: 999px;
  background: var(--today);
  color: #fff;
  font-family: inherit;
  font-size: .9rem;
  font-weight: 700;
  box-shadow: 0 4px 14px rgba(0, 0, 0, .28);
  cursor: pointer;
  opacity: 0;
  visibility: hidden;
  transform: translateY(10px);
  transition: opacity .25s ease, transform .25s ease, visibility .25s step-end;
}
.fab-today.show {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
  transition: opacity .25s ease, transform .25s ease, visibility .25s step-start;
}
.fab-today:active { transform: scale(.94); }
.fab-today .fab-icon { font-size: 1.15rem; line-height: 1; }
"""

# Doc-chip CSS lives inside the CSS block above (kept intact for easy
# re-enabling); strip it out at build time while DOC_CHIPS is False.
_DOC_CHIP_CSS_RULES = """.row .materials {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 2px;
}
.doc-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: .78rem;
  color: var(--primary);
  background: var(--primary-light);
  border: 1px solid var(--primary);
  border-radius: 999px;
  padding: 1px 8px;
  text-decoration: none;
  white-space: nowrap;
  line-height: 1.6;
}
.doc-chip:hover { text-decoration: underline; }
"""

if not DOC_CHIPS:
    CSS = CSS.replace(_DOC_CHIP_CSS_RULES, "")
    CSS = CSS.replace('\n    ".    materials materials";', "")
    CSS = CSS.replace('\n      "materials materials";', "")

GRID_CSS = """
.view-toggle {
  display: flex; gap: 6px;
  margin: 4px 0 14px;
}
.view-tab {
  flex: 1 1 auto;
  font-family: inherit;
  font-size: .92rem;
  font-weight: 600;
  padding: 9px 10px;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--muted);
  border-radius: 8px;
  cursor: pointer;
}
.view-tab.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}
.view-panel-hidden { display: none; }

.week-grid { margin-bottom: 22px; }
.week-grid-title {
  font-size: .88rem; font-weight: 700; color: var(--primary);
  margin: 0 0 6px; text-transform: uppercase; letter-spacing: .03em;
}
.grid-scroll { overflow-x: auto; border: 1px solid var(--border); border-radius: 8px; }
.wgrid {
  display: grid;
  grid-template-columns: 56px repeat(18, minmax(38px, 1fr));
  grid-auto-rows: minmax(40px, auto);
  background: var(--card);
  min-width: 780px;
}
.wg-corner {
  position: sticky; left: 0; z-index: 2;
  background: var(--card);
  border-bottom: 1px solid var(--border);
  border-right: 1px solid var(--border);
}
.wg-hour {
  display: flex; align-items: center; justify-content: space-between;
  font-size: .68rem; font-weight: 600; color: var(--muted);
  padding: 3px 4px 3px 5px;
  border-bottom: 1px solid var(--border);
  border-left: 1px solid var(--border);
  white-space: nowrap;
}
.wg-daylabel {
  position: sticky; left: 0; z-index: 2;
  display: flex; align-items: center;
  font-size: .8rem; font-weight: 700;
  padding: 4px 6px;
  border-bottom: 1px solid var(--border);
  border-right: 1px solid var(--border);
}
.wg-daylabel.wg-today { outline: 2px solid var(--today); outline-offset: -2px; }
.wg-link-flash {
  outline: 2px solid var(--today); outline-offset: -2px;
  animation: wg-link-pulse 1.5s ease-out;
}
@keyframes wg-link-pulse {
  0% { background-color: #fff3a0; }
  100% { background-color: transparent; }
}
.wg-free {
  background: repeating-linear-gradient(45deg, #eef0f3, #eef0f3 6px, #e6e8ec 6px, #e6e8ec 12px);
  border-bottom: 1px solid var(--border);
  border-left: 1px solid var(--border);
}
.wg-session {
  display: flex; flex-direction: column; justify-content: center; gap: 1px;
  padding: 3px 5px;
  border-bottom: 1px solid var(--border);
  border-left: 1px solid var(--border);
  overflow: hidden;
  font-size: .74rem;
  line-height: 1.2;
  cursor: pointer;
}
.wg-topic {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-weight: 600;
}
.wg-meta {
  display: flex; gap: 4px; align-items: baseline;
  font-size: .68rem; opacity: .85;
  overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
}
.wg-room { opacity: .75; }
.wg-cancelled { opacity: .55; }
.wg-cancelled .wg-topic { text-decoration: line-through; }

.wg-mon.wg-session, .wg-mon.wg-daylabel { background: var(--grid-mon); color: var(--grid-mon-text); }
.wg-tue.wg-session, .wg-tue.wg-daylabel { background: var(--grid-tue); color: var(--grid-tue-text); }
.wg-wed.wg-session, .wg-wed.wg-daylabel { background: var(--grid-wed); color: var(--grid-wed-text); }
.wg-thu.wg-session, .wg-thu.wg-daylabel { background: var(--grid-thu); color: var(--grid-thu-text); }
.wg-fri.wg-session, .wg-fri.wg-daylabel { background: var(--grid-fri); color: var(--grid-fri-text); }

@media (max-width: 620px) {
  .wgrid { grid-template-columns: 48px repeat(18, minmax(32px, 1fr)); min-width: 680px; }
  .wg-topic, .wg-meta { font-size: .66rem; }
}

.wg-modal-backdrop {
  position: fixed; inset: 0;
  background: rgba(15, 23, 42, .55);
  backdrop-filter: blur(2px);
  z-index: 60;
  display: none;
  align-items: center; justify-content: center;
  padding: 16px;
}
.wg-modal-backdrop.show { display: flex; }
.wg-modal-card {
  position: relative;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, .35);
  max-width: 420px;
  width: 100%;
  padding: 20px 20px 18px;
  white-space: normal;
}
.wg-modal-close {
  position: absolute; top: 10px; right: 10px;
  width: 28px; height: 28px;
  border: none; border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-size: 1rem; line-height: 1;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.wg-modal-close:hover { background: var(--primary-light); color: var(--primary); }
.wg-modal-time {
  font-size: 1.05rem; font-weight: 700; color: var(--primary);
  margin: 0 0 8px;
}
.wg-modal-topic {
  font-size: 1.05rem; font-weight: 700;
  margin: 0 0 10px;
  line-height: 1.4;
}
.wg-modal-topic.wg-modal-cancelled { text-decoration: line-through; color: var(--muted); }
.wg-modal-pills { display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 12px; }
.wg-modal-pills .pill {
  font-size: .8rem; font-weight: 600;
  padding: 2px 9px;
  border-radius: 999px;
  white-space: nowrap;
}
.wg-modal-row {
  font-size: .88rem; color: var(--muted);
  margin: 0 0 4px;
  display: flex; gap: 6px;
}
.wg-modal-row .wg-modal-label { font-weight: 600; color: inherit; min-width: 64px; flex: 0 0 auto; }
.wg-modal-row .wg-modal-value { color: #1f2937; }

@media (max-width: 480px) {
  .wg-modal-card { padding: 16px 16px 14px; width: auto; }
}
"""

CSS = CSS + GRID_CSS

JS = """
(function () {
  var days = Array.prototype.slice.call(document.querySelectorAll('.day[data-date]'));
  if (!days.length) return;

  var now = new Date();
  var todayStr = now.getFullYear() + '-' +
    String(now.getMonth() + 1).padStart(2, '0') + '-' +
    String(now.getDate()).padStart(2, '0');

  var first = days[0].getAttribute('data-date');
  var last = days[days.length - 1].getAttribute('data-date');

  var target, doHighlight;
  if (todayStr < first) {
    target = days[0];
    doHighlight = false;
  } else if (todayStr > last) {
    target = days[days.length - 1];
    doHighlight = false;
  } else {
    var exact = null, upcoming = null;
    days.forEach(function (sec) {
      var d = sec.getAttribute('data-date');
      if (d === todayStr) exact = sec;
      if (!upcoming && d >= todayStr) upcoming = sec;
    });
    target = exact || upcoming || days[days.length - 1];
    doHighlight = true;
  }

  if (doHighlight && target) {
    // label reflects reality: 'วันนี้' only when there's a real session today,
    // else 'ถัดไป' (next class, e.g. weekend/holiday)
    var label = exact ? 'วันนี้' : 'ถัดไป';
    target.classList.add('today');
    var head = target.querySelector('.day-head-text') || target.querySelector('.day-head');
    if (head && !head.querySelector('.today-badge')) {
      var badge = document.createElement('span');
      badge.className = 'today-badge';
      badge.textContent = label;
      head.appendChild(badge);
    }
    var fabLabel = document.getElementById('fabLabel');
    if (fabLabel) {
      fabLabel.textContent = 'วันนี้';
    }
  }

  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
})();

(function () {
  var fab = document.getElementById('fabToday');
  if (!fab) return;

  function toggleFab() {
    if (window.scrollY > 300) {
      fab.classList.add('show');
    } else {
      fab.classList.remove('show');
    }
  }
  window.addEventListener('scroll', toggleFab, { passive: true });
  toggleFab();

  fab.addEventListener('click', function () {
    var gridPanel = document.getElementById('gridView');
    var gridActive = gridPanel && !gridPanel.classList.contains('view-panel-hidden');
    var todayStr = (function () {
      var n = new Date();
      return n.getFullYear() + '-' +
        String(n.getMonth() + 1).padStart(2, '0') + '-' +
        String(n.getDate()).padStart(2, '0');
    })();
    if (gridActive) {
      // weekly/grid view: scroll to the week-grid whose Monday matches this week's Monday,
      // so it also works when today is a weekend/holiday (no cell exists for those days).
      var weekGrids = Array.prototype.slice.call(document.querySelectorAll('.week-grid'));
      var targetWeek = null;
      var mondayOfToday = (function () {
        var now = new Date();
        var d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); // back to Monday (getDay: Sun=0..Sat=6)
        return d.getFullYear() + '-' +
          String(d.getMonth() + 1).padStart(2, '0') + '-' +
          String(d.getDate()).padStart(2, '0');
      })();
      weekGrids.forEach(function (wg) {
        if (targetWeek) return;
        var first = wg.querySelector('.wg-daylabel[data-date]');
        if (first && first.getAttribute('data-date') === mondayOfToday) targetWeek = wg;
      });
      // fallback: week whose span contains today
      if (!targetWeek) {
        weekGrids.forEach(function (wg) {
          if (targetWeek) return;
          var dates = Array.prototype.slice.call(wg.querySelectorAll('.wg-daylabel[data-date]'))
            .map(function (c) { return c.getAttribute('data-date'); })
            .filter(Boolean).sort();
          if (dates.length && todayStr >= dates[0] && todayStr <= dates[dates.length - 1]) targetWeek = wg;
        });
      }
      if (targetWeek) {
        targetWeek.scrollIntoView({ behavior: 'smooth', block: 'start' });
        var c = targetWeek.querySelector('.wg-daylabel[data-date="' + todayStr + '"]');
        if (c) {
          c.classList.add('wg-link-flash');
          setTimeout(function () { c.classList.remove('wg-link-flash'); }, 1500);
        }
      } else {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    } else {
      var todayEl = document.querySelector('.day.today');
      if (todayEl) {
        todayEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
      } else {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }
  });
})();

(function () {
  var cells = Array.prototype.slice.call(document.querySelectorAll('.wg-daylabel[data-date]'));
  if (!cells.length) return;

  var now = new Date();
  var todayStr = now.getFullYear() + '-' +
    String(now.getMonth() + 1).padStart(2, '0') + '-' +
    String(now.getDate()).padStart(2, '0');

  cells.forEach(function (cell) {
    if (cell.getAttribute('data-date') === todayStr && cell.getAttribute('data-has-class') === '1') {
      cell.classList.add('wg-today');
    }
  });
})();

(function () {
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.view-tab'));
  var gridView = document.getElementById('gridView');
  var listView = document.getElementById('listView');
  if (!tabs.length || !gridView || !listView) return;

  tabs.forEach(function (btn) {
    btn.addEventListener('click', function () {
      tabs.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var view = btn.getAttribute('data-view');
      if (view === 'list') {
        listView.classList.remove('view-panel-hidden');
        gridView.classList.add('view-panel-hidden');
      } else {
        gridView.classList.remove('view-panel-hidden');
        listView.classList.add('view-panel-hidden');
      }
    });
  });
})();

(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll('.day-week-link'));
  if (!links.length) return;

  var dateIndex = {};
  Array.prototype.slice.call(document.querySelectorAll('.wg-daylabel[data-date]')).forEach(function (cell) {
    dateIndex[cell.getAttribute('data-date')] = cell;
  });

  links.forEach(function (link) {
    link.addEventListener('click', function () {
      var gridTab = document.querySelector('.view-tab[data-view="grid"]');
      if (gridTab) gridTab.click();

      var cell = dateIndex[link.getAttribute('data-date')];
      if (!cell) return;
      var section = cell.closest('.week-grid') || cell;
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      cell.classList.add('wg-link-flash');
      setTimeout(function () {
        cell.classList.remove('wg-link-flash');
      }, 1500);
    });
  });
})();

(function () {
  var modal = document.getElementById('wgModal');
  var sessions = Array.prototype.slice.call(document.querySelectorAll('.wg-session'));
  if (!modal || !sessions.length) return;

  var card = modal.querySelector('.wg-modal-card');
  var closeBtn = modal.querySelector('.wg-modal-close');
  var timeEl = modal.querySelector('.wg-modal-time');
  var topicEl = modal.querySelector('.wg-modal-topic');
  var pillsEl = modal.querySelector('.wg-modal-pills');
  var lectRow = modal.querySelector('.wg-modal-row-lecturer');
  var roomRow = modal.querySelector('.wg-modal-row-room');

  function setText(el, text) {
    el.textContent = text || '';
  }

  function openModal(el) {
    var topic = el.getAttribute('data-topic') || '';
    var unit = el.getAttribute('data-unit') || '';
    var lecturer = el.getAttribute('data-lecturer') || '';
    var room = el.getAttribute('data-room') || '';
    var time = el.getAttribute('data-time') || '';
    var fmtClass = el.getAttribute('data-fmt-class') || '';
    var fmtLabel = el.getAttribute('data-fmt-label') || '';
    var cancelled = el.getAttribute('data-cancelled') === '1';

    setText(timeEl, time);
    setText(topicEl, unit ? (unit + ' ' + topic) : topic);
    topicEl.classList.toggle('wg-modal-cancelled', cancelled);

    pillsEl.textContent = '';
    if (cancelled) {
      var cancelPill = document.createElement('span');
      cancelPill.className = 'pill fmt-cancelled';
      cancelPill.textContent = 'เลื่อน';
      pillsEl.appendChild(cancelPill);
    }
    if (fmtLabel) {
      var fmtPill = document.createElement('span');
      fmtPill.className = 'pill' + (fmtClass ? ' ' + fmtClass : '');
      fmtPill.textContent = fmtLabel;
      pillsEl.appendChild(fmtPill);
    }

    lectRow.style.display = lecturer ? '' : 'none';
    setText(lectRow.querySelector('.wg-modal-value'), lecturer);
    roomRow.style.display = room ? '' : 'none';
    setText(roomRow.querySelector('.wg-modal-value'), room);

    modal.classList.add('show');
  }

  function closeModal() {
    modal.classList.remove('show');
  }

  sessions.forEach(function (el) {
    el.addEventListener('click', function () {
      openModal(el);
    });
  });

  modal.addEventListener('click', function () {
    closeModal();
  });
  card.addEventListener('click', function (e) {
    e.stopPropagation();
  });
  closeBtn.addEventListener('click', closeModal);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('show')) {
      closeModal();
    }
  });
})();
"""


def build_html(course, sessions, homework, notes):
    days = with_weekends_holidays(group_by_day(sessions))
    prev_week = ""
    day_blocks = []
    for d in days:
        day_blocks.append(render_day(d, prev_week))
        if d.get("week"):
            prev_week = d["week"]
    days_html = "\n".join(day_blocks)
    grid_html = build_grid_view(sessions)

    period = course.get("period") or {}
    period_html = ""
    if period.get("start") and period.get("end"):
        period_html = f'<div class="period">{esc(thai_date(period["start"]))} – {esc(thai_date(period["end"]))}</div>'

    legend_items = "".join(
        f'<span class="pill {meta["class"]}">{esc(meta["label"])}</span>'
        for meta in FORMAT_META.values()
    ) + '<span class="pill fmt-cancelled">เลื่อน</span>'

    title = f'{course.get("name", "")} ({course.get("code", "")})'
    homework_html = render_homework(homework, notes)

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
  <div class="container">
    <header class="course-header">
      <div class="header-program">{esc(course.get('program'))}</div>
      {period_html}
    </header>

    <div class="view-toggle">
      <button type="button" class="view-tab active" data-view="list">รายวัน</button>
      <button type="button" class="view-tab" data-view="grid">ตารางรายสัปดาห์</button>
    </div>

    <div class="legend">{legend_items}</div>

    <div id="gridView" class="view-panel view-panel-hidden">
      {grid_html}
    </div>
    <div id="listView" class="view-panel">
      <main>
        {days_html}
      </main>
    </div>

    <footer class="page-footer">
      สร้างจากไฟล์ schedule.md (ฉบับตรวจทานล่าสุด) — ใช้เพื่ออ้างอิงเท่านั้น กรุณาตรวจสอบประกาศทางการอีกครั้ง
    </footer>
  </div>
  <button id="fabToday" class="fab-today" type="button" aria-label="วันนี้">
    <span class="fab-icon" aria-hidden="true">👉</span><span id="fabLabel">วันนี้</span>
  </button>
  <div id="wgModal" class="wg-modal-backdrop">
    <div class="wg-modal-card" role="dialog" aria-modal="true">
      <button type="button" class="wg-modal-close" aria-label="ปิด">✕</button>
      <div class="wg-modal-time"></div>
      <div class="wg-modal-topic"></div>
      <div class="wg-modal-pills"></div>
      <div class="wg-modal-row wg-modal-row-lecturer"><span class="wg-modal-label">อาจารย์</span><span class="wg-modal-value"></span></div>
      <div class="wg-modal-row wg-modal-row-room"><span class="wg-modal-label">ห้อง</span><span class="wg-modal-value"></span></div>
    </div>
  </div>
  <script>{JS}</script>
</body>
</html>
"""


def main():
    with open("schedule.json", encoding="utf-8") as f:
        data = json.load(f)
    course = data.get("course", {})

    with open("schedule.md", encoding="utf-8") as f:
        md_text = f.read()
    sessions, homework, notes = parse_schedule_md(md_text)

    out = build_html(course, sessions, homework, notes)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(out)

    print("DONE")


if __name__ == "__main__":
    main()
