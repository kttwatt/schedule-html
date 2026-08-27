#!/usr/bin/env python3
"""Generate index.html (ตารางเรียน) from schedule.json — single offline file, no external CDN."""
import json
import html
from datetime import datetime

THAI_MONTHS = [
    "", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]

FORMAT_META = {
    "onsite":    {"label": "เรียนในห้อง (Onsite)", "class": "fmt-onsite"},
    "hybrid":    {"label": "ไฮบริด (Hybrid)",        "class": "fmt-hybrid"},
    "selfstudy": {"label": "ศึกษาด้วยตนเอง (Self-study)", "class": "fmt-selfstudy"},
    "exam":      {"label": "สอบ (Exam)",             "class": "fmt-exam"},
    "clinical":  {"label": "ฝึกปฏิบัติ (Clinical)",   "class": "fmt-clinical"},
    "sitevisit": {"label": "ดูงาน (Site visit)",      "class": "fmt-sitevisit"},
}


def thai_date(iso_date):
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return iso_date or ""
    return f"{d.day} {THAI_MONTHS[d.month]} {d.year + 543}"


def esc(s):
    return html.escape(s or "", quote=True)


def sort_key(session):
    date = session.get("date") or ""
    start = session.get("start_time") or ""
    if not start or start == "-":
        start = "99:99"
    return (date, start)


def render_pill(fmt):
    meta = FORMAT_META.get(fmt)
    if not meta:
        return ""
    return f'<span class="pill {meta["class"]}">{esc(meta["label"])}</span>'


def render_session(session):
    is_exam = bool(session.get("is_exam"))
    fmt = session.get("format")
    classes = ["session"]
    if is_exam or fmt == "exam":
        classes.append("session-exam")
    elif fmt in ("selfstudy", "clinical"):
        classes.append("session-muted")
    if fmt is None and not session.get("start_time") or session.get("start_time") == "-":
        classes.append("session-nodata")

    day_th = esc(session.get("day_th"))
    date_str = esc(thai_date(session.get("date")))
    start = session.get("start_time") or ""
    end = session.get("end_time") or ""
    time_str = "" if start in ("", "-") else f"{esc(start)} – {esc(end)} น."

    topic = esc(session.get("topic"))
    unit = session.get("unit")
    unit_badge = f'<span class="unit-badge">หน่วยที่ {unit}</span>' if unit else ""

    lecturers = session.get("lecturers") or []
    lecturers_html = ""
    if lecturers:
        items = "".join(f"<li>{esc(l)}</li>" for l in lecturers)
        lecturers_html = f'<ul class="lecturers">{items}</ul>'

    room = session.get("room")
    room_html = f'<span class="room">📍 {esc(room)}</span>' if room else ""

    pill_html = render_pill(fmt)
    exam_badge = '<span class="pill fmt-exam">สอบ</span>' if is_exam and fmt != "exam" else ""

    notes = session.get("notes") or []
    notes_html = ""
    if notes:
        items = "".join(f"<li>{esc(n)}</li>" for n in notes)
        notes_html = f'<ul class="notes">{items}</ul>'

    moved_from = session.get("moved_from")
    moved_html = f'<div class="moved">↩ ย้ายมาจากวันที่ {esc(thai_date(moved_from))}</div>' if moved_from else ""

    materials = session.get("materials") or []
    materials_html = ""
    if materials:
        items = "".join(
            f'<li><a href="{esc(m)}">{esc(m.split("/")[-1])}</a></li>' for m in materials
        )
        materials_html = f'<ul class="materials">{items}</ul>'

    summary = session.get("summary")
    summary_html = f'<div class="summary">📝 {esc(summary)}</div>' if summary else ""

    return f"""
      <article class="{' '.join(classes)}">
        <div class="session-time">
          <div class="day">{day_th}</div>
          <div class="date">{date_str}</div>
          {f'<div class="time">{time_str}</div>' if time_str else ''}
        </div>
        <div class="session-body">
          <div class="session-head">
            <h3 class="topic">{topic}</h3>
            <div class="badges">{unit_badge}{pill_html}{exam_badge}</div>
          </div>
          {lecturers_html}
          {f'<div class="meta-row">{room_html}</div>' if room_html else ''}
          {moved_html}
          {notes_html}
          {summary_html}
          {materials_html}
        </div>
      </article>"""


def render_week(week):
    sessions = sorted(week.get("sessions") or [], key=sort_key)
    sessions_html = "\n".join(render_session(s) for s in sessions)
    dates = [s.get("date") for s in sessions if s.get("date")]
    range_str = ""
    if dates:
        range_str = f'<span class="week-range">{esc(thai_date(min(dates)))} – {esc(thai_date(max(dates)))}</span>'
    return f"""
    <section class="week">
      <h2 class="week-header"><span class="week-label">{esc(week.get('label'))}</span>{range_str}</h2>
      <div class="sessions">
        {sessions_html}
      </div>
    </section>"""


CSS = """
:root {
  --bg: #f5f7fb;
  --card-bg: #ffffff;
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
  --selfstudy-light: #f0f1f3;
  --clinical: #059669;
  --clinical-light: #e6f7f1;
  --sitevisit: #d97706;
  --sitevisit-light: #fdf2e2;
  --radius: 14px;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "Noto Sans Thai", "Sarabun", "TH Sarabun New", -apple-system, BlinkMacSystemFont,
    "Segoe UI", system-ui, sans-serif;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

.container {
  max-width: 880px;
  margin: 0 auto;
  padding: 20px 16px 64px;
}

header.course-header {
  background: linear-gradient(135deg, var(--primary) 0%, #1d4ed8 100%);
  color: #fff;
  border-radius: var(--radius);
  padding: 28px 24px;
  margin-bottom: 20px;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.25);
}

header.course-header .code {
  font-size: 0.9rem;
  opacity: 0.85;
  letter-spacing: 0.02em;
  margin-bottom: 4px;
}

header.course-header h1 {
  margin: 0 0 10px;
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.35;
}

header.course-header .program {
  font-size: 0.92rem;
  opacity: 0.92;
  margin-bottom: 4px;
}

header.course-header .period {
  font-size: 0.85rem;
  opacity: 0.8;
}

.legend {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 18px;
  margin-bottom: 24px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  align-items: center;
}

.legend .legend-title {
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--muted);
  margin-right: 4px;
}

.week {
  margin-bottom: 30px;
}

.week-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text);
  border-bottom: 2px solid var(--primary);
  padding-bottom: 8px;
  margin: 0 0 14px;
  position: sticky;
  top: 0;
  background: var(--bg);
  z-index: 1;
  padding-top: 6px;
}

.week-label { color: var(--primary); }

.week-range {
  font-size: 0.82rem;
  font-weight: 400;
  color: var(--muted);
}

.sessions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.session {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left: 4px solid var(--primary);
  border-radius: var(--radius);
  padding: 14px 16px;
  display: flex;
  gap: 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.session-exam {
  border-left-color: var(--exam);
  background: var(--exam-light);
}

.session-muted {
  border-left-color: var(--selfstudy);
  background: #fafafa;
}

.session-nodata {
  border-left-color: var(--border);
  border-style: dashed;
  opacity: 0.75;
}

.session-time {
  flex: 0 0 92px;
  text-align: center;
  padding-top: 2px;
}

.session-time .day {
  font-weight: 700;
  font-size: 0.92rem;
}

.session-time .date {
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 2px;
}

.session-time .time {
  margin-top: 6px;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-light);
  border-radius: 8px;
  padding: 3px 6px;
}

.session-exam .session-time .time {
  color: var(--exam);
  background: #fbdada;
}

.session-body {
  flex: 1;
  min-width: 0;
}

.session-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  flex-wrap: wrap;
}

.topic {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: var(--text);
  flex: 1 1 auto;
  min-width: 180px;
}

.session-exam .topic { color: var(--exam); }

.badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.pill {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 999px;
  white-space: nowrap;
}

.unit-badge {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 999px;
  background: #eef2f7;
  color: var(--muted);
  white-space: nowrap;
}

.fmt-onsite    { background: var(--primary-light); color: var(--primary); }
.fmt-hybrid    { background: var(--hybrid-light);   color: var(--hybrid); }
.fmt-selfstudy { background: var(--selfstudy-light);color: var(--selfstudy); }
.fmt-exam      { background: #fbdada;               color: var(--exam); }
.fmt-clinical  { background: var(--clinical-light); color: var(--clinical); }
.fmt-sitevisit { background: var(--sitevisit-light);color: var(--sitevisit); }

.lecturers {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  font-size: 0.85rem;
  color: var(--muted);
}

.lecturers li::before { content: "👤 "; }
.lecturers li { margin-top: 2px; }

.meta-row {
  margin-top: 6px;
  font-size: 0.82rem;
  color: var(--muted);
}

.moved {
  margin-top: 8px;
  font-size: 0.8rem;
  color: var(--sitevisit);
  background: var(--sitevisit-light);
  border-radius: 8px;
  padding: 5px 9px;
  display: inline-block;
}

.notes {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 0.8rem;
  color: var(--muted);
  font-style: italic;
}

.summary {
  margin-top: 8px;
  font-size: 0.8rem;
  color: var(--clinical);
}

.materials {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
  font-size: 0.8rem;
}

.materials li::before { content: "📎 "; }
.materials a {
  color: var(--primary);
  text-decoration: none;
}
.materials a:hover { text-decoration: underline; }

footer.page-footer {
  text-align: center;
  color: var(--muted);
  font-size: 0.78rem;
  margin-top: 30px;
}

@media (max-width: 560px) {
  .session { flex-direction: column; gap: 6px; }
  .session-time {
    flex-direction: row;
    justify-content: space-between;
    text-align: left;
    display: flex;
    align-items: center;
    gap: 8px;
    padding-top: 0;
    flex: none;
  }
  .session-time .date { margin-top: 0; }
  header.course-header h1 { font-size: 1.25rem; }
  .week-header { font-size: 1.02rem; }
}
"""


def build_html(data):
    course = data.get("course", {})
    weeks = data.get("weeks", [])

    weeks_html = "\n".join(render_week(w) for w in weeks)

    period = course.get("period") or {}
    period_html = ""
    if period.get("start") and period.get("end"):
        period_html = f'<div class="period">📅 {esc(thai_date(period["start"]))} – {esc(thai_date(period["end"]))}</div>'

    legend_items = "".join(
        f'<span class="pill {meta["class"]}">{esc(meta["label"])}</span>'
        for meta in FORMAT_META.values()
    )

    title = f'{course.get("name", "")} ({course.get("code", "")})'

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
      <div class="code">{esc(course.get('code'))}</div>
      <h1>{esc(course.get('name'))}</h1>
      <div class="program">{esc(course.get('program'))}</div>
      {period_html}
    </header>

    <div class="legend">
      <span class="legend-title">คำอธิบายสัญลักษณ์:</span>
      {legend_items}
    </div>

    <main>
      {weeks_html}
    </main>

    <footer class="page-footer">
      สร้างจากไฟล์ schedule.json — ตารางเรียนฉบับนี้ใช้เพื่ออ้างอิงเท่านั้น กรุณาตรวจสอบประกาศทางการอีกครั้ง
    </footer>
  </div>
</body>
</html>
"""


def main():
    with open("schedule.json", encoding="utf-8") as f:
        data = json.load(f)

    out = build_html(data)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(out)

    print("DONE")


if __name__ == "__main__":
    main()
