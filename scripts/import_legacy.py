#!/usr/bin/env python3
"""Import the legacy audit CSV and chapter tables into canonical JSON data."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_REF = 'dd169a86770f77fd96aa8008b4dc24eb5466902b'
CSV_PATH = ROOT / "data" / "audit-index.csv"
AUDIT_DIR = ROOT / "audit"
HANDBOOK_PATH = ROOT / "data" / "handbook.json"
SCOPE_PATH = ROOT / "data" / "review-scope.json"
CSV_FIELDS = [
    "chapter", "item", "title", "original_grade", "audit_status", "study_design",
    "source_status", "numeric_check", "causal_strength", "population_match", "last_verified",
]
EMOJI_STATUS = [("🔴", "incorrect"), ("🔵", "disputed"), ("🟠", "uncertain"), ("🟡", "qualified"), ("✅", "trusted"), ("⚪", "experience")]

POLICY_CHAPTER_RE = re.compile(
    r"法律|红线|钱|医保|医疗保险|税|签证|留学|出国|租房|买房|工伤|创业|生意|离职|社保|死亡|办什么|保险|福利|救助"
)
POLICY_CUE_RE = re.compile(
    r"政策|规定|法规|法律|签证|医保|医疗保险|税务|税率|工伤|社保|入境|出境|补贴|福利|救助|申请资格|申请条件|办理流程|现行|截至|最新|每年|更新|调整|试点|各地|本地|当地|地方|各省|不同地区|版本"
)
POLICY_DOMAIN_RE = re.compile(
    r"兵役|退役|招录|公务员|创业担保贷款|育儿补贴|补贴|税务|税率|签证|医保|医疗保险|社保|职业伤害保障|学籍|招生|产假|条例|法规|法律|法第|工伤|入境|出境|年休假|免税"
)
NUMBER_RE = re.compile(r"(?:\d{4}[-年/.]\d{1,2}|\d+(?:\.\d+)?\s*(?:元|万|亿|美元|英镑|欧元|天|日|个月|月|年|周|小时|分钟|%|％|岁|倍|个工作日|工作日|比例|税率|点))")
ISSUE_PATTERNS = [
    ("legacy_or_unverified_status", re.compile(r"🟠|🔵|🔴|证据不足|待核实|待验证|未核实|未核验|尚未核验|争议|有争议|过时|已过时|错误|不准确|不成立|需核实|需要核实|需更新|需要更新")),
    ("potentially_overstated_or_incomplete", re.compile(r"安全隐患|误导|不完整|不是全国|并非全国|过度|一概|不能一概|不能直接外推|不可直接外推|标题.*(?:宽|窄|过度|简化)|证据映射不严谨|外推明显")),
]


def split_md_row(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", line)[1:-1]]


def clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def audit_rows(path: Path) -> tuple[str, str, dict[int, dict[str, str]]]:
    relative = path.relative_to(ROOT).as_posix()
    original = subprocess.run(
        ["git", "show", f"{LEGACY_REF}:{relative}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    text = original.stdout.decode("utf-8-sig")
    title_match = re.search(r"^#\s*第\s*\d+\s*章《([^》]+)》", text, re.M)
    chapter_title = title_match.group(1).strip() if title_match else path.stem.split("-", 1)[-1]
    verified_match = re.search(r"last_verified\s*[:：]\s*(\d{4}-\d{2}-\d{2})", text)
    verified = verified_match.group(1) if verified_match else ""
    rows: dict[int, dict[str, str]] = {}
    for line in text.splitlines():
        cells = split_md_row(line)
        if len(cells) < 5:
            continue
        if cells[0] in ("原编号", "编号") or re.fullmatch(r"[-: ]+", "".join(cells)):
            continue
        if not cells[0].isdigit():
            continue
        number = int(cells[0])
        if number in rows:
            raise ValueError(f"{path.name}: audit 原编号 {number} 重复")
        rows[number] = {
            "original_title": clean_cell(cells[1]),
            "original_grade": clean_cell(cells[2]),
            "audit_status": clean_cell(cells[3]),
            "summary": clean_cell(cells[4]),
        }
    return chapter_title, verified, rows


def classify_status(status: str) -> str:
    # Mixed emoji: choose the more cautious category.
    present = [category for glyph, category in EMOJI_STATUS if glyph in status]
    if present:
        return max(present, key={"trusted": 0, "experience": 0, "qualified": 1, "uncertain": 2, "disputed": 3, "incorrect": 4}.get)
    lowered = status.lower()
    if status.startswith(("经验建议", "只能视为经验建议", "常见财务规划经验值")):
        return "experience"
    if any(word in status for word in ("错误", "不准确", "不成立", "已过时")):
        return "incorrect"
    if any(word in status for word in ("争议", "冲突", "分歧")):
        return "disputed"
    if any(word in status for word in ("待核", "待验证", "证据不足", "未核验", "需核实", "需更新")):
        return "uncertain"
    if any(word in status for word in ("限定", "但", "需", "仍有", "部分", "谨慎", "不足", "较弱", "不宜")):
        return "qualified"
    if any(word in status for word in ("可信", "已核验", "核心建议", "核心结论")):
        return "trusted"
    return "uncertain"


def candidate_reasons(chapter_title: str, original_title: str, summary: str, status: str) -> list[str]:
    full = "\n".join((original_title, summary, status))
    reasons: list[str] = []
    for reason_code, pattern in ISSUE_PATTERNS:
        hits = sorted(set(pattern.findall(full)))
        if hits:
            reasons.append(f"{reason_code}: 命中表述「{'、'.join(hits)}」")
    policy_chapter = bool(POLICY_CHAPTER_RE.search(chapter_title))
    policy_domain = bool(POLICY_DOMAIN_RE.search(full))
    if policy_chapter or policy_domain:
        numeric_hits = sorted(set(NUMBER_RE.findall(full)))
        cues = sorted(set(POLICY_CUE_RE.findall(full)))
        source = "动态政策主题章节" if policy_chapter else "涉及具体政策领域"
        if numeric_hits:
            reasons.append(f"dynamic_policy_number: {source}出现日期、金额、比例或期限数字「{'、'.join(numeric_hits)}」")
        if cues:
            reasons.append(f"dynamic_policy_cue: {source}包含时效提示「{'、'.join(cues)}」")
    return reasons


def refuse_preserved_results(force: bool) -> None:
    if force:
        return
    for path in (HANDBOOK_PATH, SCOPE_PATH):
        if not path.exists():
            continue
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records = prior.get("items", []) if isinstance(prior, dict) else []
        if isinstance(records, dict):
            records = list(records.values())
        if path == SCOPE_PATH and isinstance(prior, dict):
            records = prior.get("items", prior.get("candidates", []))
            if isinstance(records, dict):
                records = list(records.values())
        for record in records:
            if not isinstance(record, dict):
                continue
            outcome = record.get("review_outcome", record.get("outcome", "legacy"))
            if outcome not in (None, "", "legacy", "unresolved"):
                raise SystemExit(f"拒绝覆盖已有复核结果：{path.relative_to(ROOT)} 中存在 outcome={outcome!r}；首次重新导入请传 --force")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="覆盖已有新复核结果；用于首次重新导入或明确重置")
    args = parser.parse_args()
    refuse_preserved_results(args.force)

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_FIELDS:
            raise SystemExit(f"CSV 字段不符：{reader.fieldnames!r}")
        csv_records = list(reader)

    audit_files = sorted(AUDIT_DIR.glob("*.md"))
    if len(audit_files) != 32:
        raise SystemExit(f"期望32篇audit文件，实际{len(audit_files)}篇")
    chapter_map = {}
    audit_map = {}
    chapter_titles = {}
    for path in audit_files:
        match = re.match(r"^(\d+)-", path.name)
        if not match:
            raise SystemExit(f"章节文件名没有编号：{path.name}")
        chapter_no = int(match.group(1))
        title, chapter_verified, rows = audit_rows(path)
        chapter_map[chapter_no] = {"number": chapter_no, "title": title, "file": path.relative_to(ROOT).as_posix()}
        chapter_titles[chapter_no] = title
        for item_no, record in rows.items():
            audit_map[(chapter_no, item_no)] = {**record, "chapter_verified": chapter_verified}

    seen = Counter()
    items = []
    candidates = []
    ambiguities = []
    for source in csv_records:
        chapter_no, item_no = int(source["chapter"]), int(source["item"])
        key = (chapter_no, item_no)
        seen[key] += 1
        audit = audit_map.get(key)
        if audit is None:
            ambiguities.append({"key": key, "kind": "missing_audit_row", "csv_title": source["title"]})
            continue
        item = dict(source)
        item["chapter"] = chapter_no
        item["item"] = item_no
        item.update({
            "id": f"c{chapter_no:02d}-i{item_no:03d}",
            "original_title": audit["original_title"],
            "revised_conclusion": audit["summary"],
            "conditions": "",
            "summary": audit["summary"],
            "status": classify_status(audit["audit_status"]),
            "sources": [],
            "checked_at": None,
            "verified_at": None,
            "review_outcome": "legacy",
            "change_reason": "",
            "review_reasons": [],
        })
        reasons = candidate_reasons(chapter_titles[chapter_no], audit["original_title"], audit["summary"], audit["audit_status"])
        if reasons:
            item["review_outcome"] = "unresolved"
            item["checked_at"] = "2026-10-07"
            item["change_reason"] = "结构性证据缺口：本次仅整理历史核验材料，未补足支持整条建议的一手证据。"
            item["review_reasons"] = reasons
            candidates.append({
                "id": item["id"],
                "reasons": reasons,
                "original_title": audit["original_title"],
                "original_status": audit["audit_status"],
                "outcome": "unresolved",
                "reason": "本次尚未取得足以支持整条建议的一手证据；保留历史摘要，待进一步核实。",
            })
        items.append(item)

    csv_keys = set(seen)
    audit_keys = set(audit_map)
    for key in sorted(audit_keys - csv_keys):
        ambiguities.append({"key": key, "kind": "missing_csv_row", "original_title": audit_map[key]["original_title"]})
    for key, count in seen.items():
        if count > 1:
            ambiguities.append({"key": key, "kind": "duplicate_csv_key", "count": count})
    if len(items) != 552 or len(chapter_map) != 32 or len(csv_keys) != 552 or audit_keys != csv_keys or ambiguities:
        raise SystemExit(f"关联完整性检查失败：items={len(items)}, chapters={len(chapter_map)}, CSV键={len(csv_keys)}, audit键={len(audit_keys)}, 歧义={len(ambiguities)}")

    HANDBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    HANDBOOK_PATH.write_text(json.dumps({
        "version": "2026-10-07",
        "chapters": [chapter_map[n] for n in sorted(chapter_map)],
        "items": items,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SCOPE_PATH.write_text(json.dumps({
        "version": "2026-10-07",
        "items": candidates,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = Counter(item["status"] for item in items)
    print(f"已导入：{len(items)} 条，{len(chapter_map)} 章")
    print("状态统计：" + ", ".join(f"{status}={counts[status]}" for status in ("trusted", "qualified", "uncertain", "disputed", "incorrect", "experience")))
    print(f"复核候选：{len(candidates)} 条；关联歧义：{len(ambiguities)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
