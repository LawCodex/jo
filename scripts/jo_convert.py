#!/usr/bin/env python3
"""Convert cached lob.gov.jo JSON (see jo_fetch.py) to Markdown.

Usage: jo_convert.py [RAW_DIR] [OUT_DIR]
"""
import glob
import html
import json
import os
import re
import sys
from datetime import date

import yaml
from markdownify import markdownify

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "_raw", "jo")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..")
RETRIEVED = os.environ.get("RETRIEVED", date.today().isoformat())

TYPES = {
    1: ("constitution", "constitution", "دستور"),
    2: ("laws", "law", "قانون"),
    3: ("bylaws", "bylaw", "نظام"),
    4: ("agreements", "agreement", "اتفاقية"),
    5: ("instructions", "instructions", "تعليمات"),
}
STATUS = {1: "in_force", 2: "repealed"}

LABEL_RE = re.compile(r"^(?:ال)?مادة\s*\(?\s*\d+")
ENUM_RE = re.compile(r"^(?:\(?[0-9٠-٩]+\s*[-\)\.:]|\(?[أ-ي]{1,2}\s*[-\)\.]|[-•*]\s)")


def clean_line(s):
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = s.replace("\xa0", " ").replace("\u200f", "").replace("\u200e", "")
    return re.sub(r"[ \t]+", " ", s).strip()


def html_lines(t):
    """Split article HTML into text lines (tables are kept as Markdown tables / HTML)."""
    t = t or ""
    t = t.replace("\r", "")
    return [x for x in (clean_line(p) for p in re.split(r"<br\s*/?>|</p>|</div>|\n", t, flags=re.I)) if x]


def md_escape(line):
    # avoid accidental Markdown structures at line start
    if re.match(r"^(#|>|\d+\.\s|[-+*]\s|={3,}|-{3,})", line):
        return "\\" + line
    return line


def body_text(t):
    if t and "<table" in t.lower():
        md = markdownify(t, heading_style="ATX", strip=["img", "a", "span", "font"])
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        return md
    out = []
    for ln in html_lines(t):
        if out and ENUM_RE.match(ln):
            out.append("")
        out.append(md_escape(ln))
    return "\n".join(out)


def heading_for(line):
    if re.match(r"^(الكتاب|الباب|الجزء)", line):
        return "##"
    if re.match(r"^الفصل", line):
        return "###"
    if re.match(r"^(القسم|الفرع)", line):
        return "####"
    return None


def render_articles(arts):
    out = []
    for a in arts:
        t = a.get("Article") or ""
        num = a.get("Article_Number")
        lines = html_lines(t) if "<table" not in t.lower() else []
        hit = None
        for i, ln in enumerate(lines[:8]):
            if LABEL_RE.match(ln):
                hit = i
                break
        if hit is not None:
            pend = None
            for ln in lines[:hit]:
                h = heading_for(ln)
                if h:
                    out.append(f"{h} {ln}")
                    out.append("")
                    pend = len(out) - 2
                elif pend is not None:
                    out[pend] += " — " + ln
                else:
                    out.append(f"**{md_escape(ln)}**")
                    out.append("")
            label = re.sub(r"[\s:\-–]+$", "", lines[hit])
            out.append(f"##### {label}")
            out.append("")
            rest = lines[hit + 1:]
            buf = []
            for ln in rest:
                if buf and ENUM_RE.match(ln):
                    buf.append("")
                buf.append(md_escape(ln))
            if buf:
                out.append("\n".join(buf))
                out.append("")
            continue
        if num is not None:
            out.append(f"##### المادة {num}")
            out.append("")
        b = body_text(t)
        if b:
            out.append(b)
            out.append("")
    return "\n".join(out).strip() + "\n"


def iso(d):
    return d[:10] if d else None


def main():
    counts = {}
    for fn in sorted(glob.glob(os.path.join(RAW, "det", "*", "*.json"))):
        d = json.load(open(fn))
        item, det = d["item"], d.get("details") or {}
        t = item["Type"]
        dirname, typ, _ = TYPES[t]
        legs = det.get("Legislation") or [{}]
        leg = legs[0]
        arts = det.get("Articles") or []
        name = re.sub(r"\s+", " ", item["Name"]).strip()
        year = item.get("Year") or leg.get("Year") or 0
        number = item.get("Number")
        pid = item["pmk_ID"]
        status = STATUS.get(leg.get("Status"), None) or (
            "in_force" if item.get("Status_AR") == "ساري" else
            "repealed" if item.get("Status_AR") == "غير ساري" else "unknown")
        mods = d.get("modified") or []
        amended = []
        for m in mods:
            s = (m.get("ModName") or "").strip()
            if m.get("ModNumber") and m.get("ModNumber") not in ("0", 0):
                s += f" رقم {m['ModNumber']}"
            if m.get("Year"):
                s += f" لسنة {m['Year']}"
            if s and s not in amended:
                amended.append(s)
        fm = {
            "title": name,
            "identifier": f"lob.gov.jo:{t}:{pid}",
            "number": number if number else None,
            "year": year or None,
            "type": typ,
            "type_ar": item.get("TypeArName") or TYPES[t][2],
            "jurisdiction": "jo",
            "language": "ar",
            "date": iso(leg.get("Magazine_Date")),
            "in_force_from": iso(leg.get("Active_Date")),
            "gazette_number": leg.get("Magazine_Number"),
            "gazette_page": leg.get("Magazine_Page_Number"),
            "last_amended": str(max(m["Year"] for m in mods if m.get("Year"))) if any(m.get("Year") for m in mods) else None,
            "amended_by": amended or None,
            "status": status,
            "status_ar": item.get("Status_AR"),
            "source": f"https://www.lob.gov.jo/?v=2&lang=ar#!/LegislationDetails?LegislationID={pid}&LegislationType={t}&isMod=false",
            "retrieved": RETRIEVED,
        }
        fm = {k: v for k, v in fm.items() if v is not None}
        intro = (leg.get("Introduction") or "").strip()
        body = []
        body.append(f"# {name}\n")
        if intro:
            body.append(body_text(intro) + "\n")
        if arts:
            body.append(render_articles(arts))
        else:
            body.append("*(لا يتضمن المصدر نص مواد لهذا التشريع.)*\n")
        if t == 1:
            rel = os.path.join("ar", dirname, f"{year}-constitution-{pid}.md")
        else:
            num = f"{int(number):03d}" if isinstance(number, int) and number > 0 else "000"
            rel = os.path.join("ar", dirname, str(year or "undated"), f"{year}-{num}-{pid}.md")
        path = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("---\n")
            f.write(yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=1000))
            f.write("---\n\n")
            f.write("\n".join(body).rstrip() + "\n")
        key = (dirname, status)
        counts[key] = counts.get(key, 0) + 1
    for k, v in sorted(counts.items()):
        print(k, v)


if __name__ == "__main__":
    main()
