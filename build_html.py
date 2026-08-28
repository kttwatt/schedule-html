#!/usr/bin/env python3
"""Generate index.html (ตารางเรียน) from schedule.md (authoritative) + schedule.json (course meta).

schedule.md is the hand-reconciled source of truth: it already reflects cancellations
("เลื่อน", marked with ❌) and sessions moved to later dates. schedule.json is only used
for course header metadata (code/name/program/period).
"""
import json
import re
import html
from datetime import datetime
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

    return f'<div class="{" ".join(classes)}">{time_html}{topic_html}{who_html}{pill_html}{materials_html}</div>'


def render_day(day, prev_week):
    week_html = ""
    if day["week"] and day["week"] != prev_week:
        week_html = f'<div class="week-div">{esc(day["week"])}</div>'
    rows_html = "\n".join(render_session_row(s) for s in day["sessions"])
    date_attr = f' data-date="{esc(day["date_iso"])}"' if day.get("date_iso") else ""
    return week_html + f"""<section class="day"{date_attr}>
  <div class="day-head">{esc(day["date_text"])}</div>
  {rows_html}
</section>"""


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
  --today: #b45309;
  --today-light: #fef3e0;
  --today-text: #92400e;
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
.day-head {
  font-size: .96rem; font-weight: 700;
  background: var(--card);
  border-radius: 6px;
  padding: 4px 8px;
  margin-top: 6px;
  position: sticky; top: 0;
  border: 1px solid var(--border);
}

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
  display: grid;
  grid-template-columns: 6.5em 1fr auto;
  grid-template-areas:
    "time topic pill"
    ".    who   who"
    ".    materials materials";
  column-gap: 8px;
  row-gap: 1px;
  align-items: baseline;
  padding: 5px 8px;
  border-bottom: 1px solid var(--border);
  font-size: .96rem;
}
.row:last-child { border-bottom: none; }

.row .time {
  grid-area: time;
  font-weight: 600;
  color: var(--primary);
  font-variant-numeric: tabular-nums;
  font-size: .9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
.row .topic { grid-area: topic; min-width: 0; }
.row .who { grid-area: who; font-size: .88rem; color: var(--muted); min-width: 0; }
.row .materials {
  grid-area: materials;
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
  grid-area: pill;
  justify-self: end;
  align-self: start;
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
  .row {
    grid-template-columns: 1fr auto;
    grid-template-areas:
      "time  time"
      "topic pill"
      "who   who"
      "materials materials";
    row-gap: 3px;
    column-gap: 6px;
  }
  .row .time {
    font-size: .85rem;
    font-weight: 600;
    color: var(--muted);
    padding-bottom: 3px;
    margin-bottom: 1px;
    border-bottom: 1px dashed var(--border);
    overflow: visible;
    text-overflow: clip;
  }
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
  grid-area: materials;
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
    target.classList.add('today');
    var head = target.querySelector('.day-head');
    if (head && !head.querySelector('.today-badge')) {
      var badge = document.createElement('span');
      badge.className = 'today-badge';
      badge.textContent = 'วันนี้';
      head.appendChild(badge);
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
    var todayEl = document.querySelector('.day.today');
    if (todayEl) {
      todayEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  });
})();
"""


def build_html(course, sessions, homework, notes):
    days = group_by_day(sessions)
    prev_week = ""
    day_blocks = []
    for d in days:
        day_blocks.append(render_day(d, prev_week))
        prev_week = d["week"]
    days_html = "\n".join(day_blocks)

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

    <div class="legend">{legend_items}</div>

    <main>
      {days_html}
    </main>

    {homework_html}

    <footer class="page-footer">
      สร้างจากไฟล์ schedule.md (ฉบับตรวจทานล่าสุด) — ใช้เพื่ออ้างอิงเท่านั้น กรุณาตรวจสอบประกาศทางการอีกครั้ง
    </footer>
  </div>
  <button id="fabToday" class="fab-today" type="button" aria-label="วันนี้">
    <span class="fab-icon" aria-hidden="true">📅</span><span>วันนี้</span>
  </button>
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
