import json
import re
import subprocess
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HANDBOOK = ROOT / "data" / "handbook.json"
OUTPUT = ROOT / "data" / "upstream-links.json"


def main():
    parser = argparse.ArgumentParser(description='提取指定上游快照中的引用入口，不代表来源已核验。')
    parser.add_argument('--upstream', type=Path, required=True)
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    book = upstream / 'book'
    handbook = json.loads(HANDBOOK.read_text(encoding="utf-8"))
    commit = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True, encoding='utf-8'
    ).strip()
    files = {
        int(match.group(1)): path
        for path in book.glob("*.md")
        if (match := re.match(r"(\d+)-", path.name))
    }
    heading_re = re.compile(r"^###\s+(\d+)[.、．]?\s*(.*?)\s*$", re.MULTILINE)
    url_re = re.compile(r"https?://[^\s<>\]\[\"']+")
    trim = ".,;:!?，。；：！？、）)]}"

    source_by_key = {}
    for chapter, path in files.items():
        content = path.read_text(encoding="utf-8")
        headings = list(heading_re.finditer(content))
        for index, heading in enumerate(headings):
            item = int(heading.group(1))
            end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
            body = content[heading.end():end]
            source_line = next(
                (line.strip() for line in body.splitlines() if line.strip().startswith("- 来源：")),
                None,
            )
            urls = [] if source_line is None else [url.rstrip(trim) for url in url_re.findall(source_line)]
            source_by_key[(chapter, item)] = (urls, source_line)

    output_items = []
    missing_keys = []
    for item in handbook["items"]:
        key = (int(item["chapter"]), int(item["item"]))
        if key not in source_by_key:
            missing_keys.append((item["id"], key))
            urls, source_line = [], None
        else:
            urls, source_line = source_by_key[key]
        output_items.append(
            {"id": item["id"], "original_source_urls": urls, "source_line": source_line,
             "mapping_note": '上游当前快照缺少同编号条目，未自动映射。' if key not in source_by_key else '按章节与原编号映射；上游内容可能已经修改，引用入口未经本次复核。'}
        )

    OUTPUT.write_text(
        json.dumps({"upstream_commit": commit, "items": output_items}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"commit={commit} items={len(output_items)} with_urls={sum(bool(x['original_source_urls']) for x in output_items)}")
    print(f'未映射编号：{missing_keys}')
    for target in ("c19-i005", "c29-i013", "c05-i034", "c32-i002", "c07-i009"):
        record = next(x for x in output_items if x["id"] == target)
        print(json.dumps(record, ensure_ascii=True))


if __name__ == "__main__":
    main()
