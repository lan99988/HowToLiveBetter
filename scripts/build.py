"""Generate all public reading formats from data/handbook.json (stdlib only)."""
import argparse
import csv
import hashlib
import html
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = {
    'trusted': ('✅', '核心结论有支持'),
    'qualified': ('🟡', '需要限定条件'),
    'uncertain': ('🟠', '证据不足 / 待核实'),
    'disputed': ('🔵', '存在争议'),
    'incorrect': ('🔴', '错误 / 过时'),
    'experience': ('⚪', '经验建议'),
}
CSV_FIELDS = ['chapter', 'item', 'title', 'original_grade', 'audit_status',
              'study_design', 'source_status', 'numeric_check', 'causal_strength',
              'population_match', 'last_verified']


def read_data():
    data = json.loads((ROOT / 'data/handbook.json').read_text(encoding='utf-8'))
    items = data['items']
    assert len(items) == 552 and len(data['chapters']) == 32, 'Expected 552 items / 32 chapters'
    assert len({r['id'] for r in items}) == 552, 'Duplicate item ID'
    for r in items:
        assert r['id'] == f"c{r['chapter']:02d}-i{r['item']:03d}", r['id']
        assert r['status'] in STATUS and r['summary'] and r['revised_conclusion'], r['id']
        assert r['original_title'] and r['last_verified'], r['id']
        for s in r['sources']:
            assert s['url'].startswith('https://'), r['id']
        for url in r.get('original_source_urls', []):
            assert url.startswith(('https://', 'http://')), r['id']
        if r['review_outcome'] == 'verified':
            assert r['sources'] and r['checked_at'] and r['verified_at'], r['id']
        if r['review_outcome'] in ('unresolved', 'contradicted'):
            assert r['change_reason'], r['id']
    return data


def md(value):
    return str(value).replace('|', '\\|').replace('\n', '<br>')


def chapter_markdown(chapter, items):
    lines = [f"# 第 {chapter['number']} 章 · {chapter['title']}", '',
             '> 由统一数据源自动生成。旧核验日期与本次核验日期分开记录；历史标记不等于本次已验证。', '']
    for r in items:
        icon, label = STATUS[r['status']]
        lines += [f"<a id=\"{r['id']}\"></a>", '', f"## {r['item']}. {icon} {label}", '',
                  r['revised_conclusion'], '', f"- 适用条件：{r['conditions'] or '未单独列出；请结合核验摘要理解，不能自动外推。'}",
                  f"- 原建议：{r['original_title']}", f"- 原等级：{r['original_grade']}；原核验说明：{r['audit_status']}",
                  f"- 历史核验日期：{r['last_verified']}",
                  f"- 本次检查日期：{r['checked_at'] or '未进行新一轮核验'}",
                  f"- 本次核验成功日期：{r['verified_at'] if r['review_outcome'] == 'verified' else '未取得新的核验成功记录'}",
                  '', '**历史核验摘要**', '', r['summary'], '', '**本次复核说明**', '',
                  r['change_reason'] or '本条保留历史核验内容，本次没有重新核验。', '', '**证据与来源**', '']
        if r['sources']:
            lines += [f"- [{s['title']}]({s['url']}) — {s.get('note', '')}" for s in r['sources']]
        else:
            lines += ['- 历史记录未附可逐条追溯的一手证据链接；本次未补足。']
        lines += ['', '**上游引用入口（未代表本次已核实）**', '']
        lines += [r.get('upstream_mapping_note', '未映射上游引用。')]
        for url in r.get('original_source_urls', []):
            lines += [f'- [上游引用]({url})']
        lines += ['']
    return '\n'.join(lines)


def outputs(data):
    result = {}
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('&', '\\u0026').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    template = (ROOT / 'src/handbook.html').read_text(encoding='utf-8')
    assert template.count('@@HANDBOOK_DATA@@') == 1
    result['index.html'] = template.replace('@@HANDBOOK_DATA@@', payload)
    csv_buffer = io.StringIO(newline='')
    writer = csv.DictWriter(csv_buffer, fieldnames=CSV_FIELDS, lineterminator='\n', extrasaction='ignore')
    writer.writeheader()
    writer.writerows(data['items'])
    result['data/audit-index.csv'] = csv_buffer.getvalue()
    chapters = []
    for ch in data['chapters']:
        body = chapter_markdown(ch, [r for r in data['items'] if r['chapter'] == ch['number']])
        result[ch['file']] = body
        chapters.append(body)
    verified = [r for r in data['items'] if r['review_outcome'] == 'verified']
    scope = json.loads((ROOT / 'data/review-scope.json').read_text(encoding='utf-8'))
    candidates = scope['items'] if isinstance(scope, dict) else scope
    lookup = {r['id']: r for r in data['items']}
    assert all(r['id'] in lookup for r in candidates)
    assert len({r['id'] for r in candidates}) == len(candidates)
    unresolved = [r for r in candidates if lookup[r['id']]['review_outcome'] != 'verified']
    report = ['# 本次重点复核记录', '', f"版本日期：{data['version']}", '',
              f"全库 552 条；固定复核清单 {len(candidates)} 条；本次取得支持并更新 {len(verified)} 条；清单中未取得整条充分证据 {len(unresolved)} 条。", '',
              '未解决记录表示仍有证据缺口，不表示已完成全文系统综述或已证明该建议错误。未取得一手支持的大多数候选仅完成历史摘要与引用结构检查，尚未新审阅证据正文。旧的 verified 字段属于历史记录，不代表本次核验。', '',
              '| 编号 | 原建议 | 纳入原因 | 本次结果 | 检查日期 | 说明 |', '|---|---|---|---|---|---|']
    for candidate in candidates:
        r = lookup[candidate['id']]
        outcome = {'verified': '取得一手支持并修订', 'unresolved': '未解决 / 待核实', 'contradicted': '原说法被证据否定', 'legacy': '尚未新核验'}.get(r['review_outcome'], r['review_outcome'])
        report.append('| ' + ' | '.join(md(x) for x in [r['id'], r['original_title'], '；'.join(candidate['reasons']), outcome, r['checked_at'] or '—', r['change_reason'] or '保留历史摘要，尚未取得新的证据。']) + ' |')
    result['REVIEW_LOG.md'] = '\n'.join(report) + '\n'
    counts = {label: sum(r['status'] == code for r in data['items']) for code, (_, label) in STATUS.items()}
    result['FINAL_AUDIT_SUMMARY.md'] = '\n'.join(['# 离线手册版本摘要', '', f"版本：{data['version']}；32 章、552 条。", '',
        '状态分类用于阅读导航；旧核验没有自动变成本次核验。', '',
        *[f'- {name}：{count} 条' for name, count in counts.items()], '',
        f'- 本次核验成功：{len(verified)} 条', f'- 重点复核清单：{len(candidates)} 条',
        f'- 清单中仍未解决：{len(unresolved)} 条', '', '[详细复核记录](REVIEW_LOG.md)', ''])
    intro = f'''# HowToLiveBetter · 更好生活离线手册

32 章、552 条生活建议与核验说明。版本：**{data['version']}**。

## 直接使用

下载本仓库的 **[index.html](index.html)**，用浏览器打开。手机请先下载文件，再选择浏览器打开；聊天软件的预览可能不执行脚本。阅读、全文搜索、章节与状态筛选不需要联网，查阅外部证据时需要联网。

支持按章连续阅读、稳定条目编号定位、复制分享摘要。所有正文、脚本和样式都在一个文件内，改名或转发不影响阅读。无注册、追踪或个人数据上传。

## 本次升级的内容边界

本次取得一手支持并修订 **{len(verified)} 条**；固定重点清单 **{len(candidates)} 条**，其中 **{len(unresolved)} 条**仍未取得整条充分证据。未复核条目保留历史日期。不要把历史“已核验”或网页新版日期理解为全部内容已重新核验。

- [重点复核记录](REVIEW_LOG.md)
- [状态与版本摘要](FINAL_AUDIT_SUMMARY.md)
- [核验方法](AUDIT_PROTOCOL.md)
- [生成及维护说明](BUILD.md)
- [传播许可与署名](LICENSE.md)

## 章节目录

'''
    intro += '\n'.join(f"{ch['number']}. [{ch['title']}]({ch['file']})" for ch in data['chapters'])
    intro += '\n\n## 全量正文\n\n下文与单文件 HTML 从同一数据源生成。\n\n'
    result['README.md'] = intro + '\n\n'.join(chapters)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Fail if generated files differ; no writes')
    args = parser.parse_args()
    generated = outputs(read_data())
    changed = []
    for name, content in generated.items():
        path = ROOT / name
        if not path.exists() or path.read_text(encoding='utf-8') != content:
            changed.append(name)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8', newline='\n')
    if args.check and changed:
        raise SystemExit('Stale generated files: ' + ', '.join(changed))
    print(f"{'Checked' if args.check else 'Generated'} {len(generated)} files; {len(changed)} changed")
    print('HTML SHA256:', hashlib.sha256(generated['index.html'].encode()).hexdigest())


if __name__ == '__main__':
    main()
