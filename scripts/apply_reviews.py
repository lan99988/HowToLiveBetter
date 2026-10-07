"""Apply recorded, human-reviewed evidence updates without changing legacy fields."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/handbook.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    updates = json.loads((ROOT / 'data/review-updates.json').read_text(encoding='utf-8'))
    refs = json.loads((ROOT / 'data/upstream-links.json').read_text(encoding='utf-8'))
    scope_path = ROOT / 'data/review-scope.json'
    scope = json.loads(scope_path.read_text(encoding='utf-8'))
    reference_map = {r['id']: r for r in refs['items']}
    records = {r['id']: r for r in data['items']}
    scope_ids = {r['id'] for r in scope['items']}
    for r in data['items']:
        entry = reference_map.get(r['id'], {})
        r['original_source_urls'] = entry.get('original_source_urls', [])
        r['upstream_mapping_note'] = entry.get('mapping_note', '未映射')
        if r['review_outcome'] == 'unresolved':
            r['change_reason'] = ('本次完成历史摘要与引用结构检查，尚未进行新的一手证据实质审阅；'
                '上游引用入口不等于已查读证据，不能凭旧来源标记确认整条建议。')
    for group, outcome in [('items', 'verified'), ('unresolved_updates', 'unresolved')]:
        for change in updates[group]:
            r = records[change['id']]
            if r['id'] not in scope_ids:
                scope['items'].append({'id': r['id'], 'reasons': ['manual_review: 逐条检查发现需要补足条件或证据映射'],
                    'original_title': r['original_title'], 'original_status': r['audit_status']})
                scope_ids.add(r['id'])
            r.update({k: v for k, v in change.items() if k != 'id'})
            r['review_outcome'] = outcome
            r['checked_at'] = updates['version']
            r['verified_at'] = updates['version'] if outcome == 'verified' else None
    # The manifest freezes selection; outcome is always derived from the canonical data.
    for entry in scope['items']:
        entry.pop('outcome', None)
        entry.pop('reason', None)
    scope['items'].sort(key=lambda r: r['id'])
    data['upstream_reference_commit'] = refs['upstream_commit']
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    scope_path.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f"Applied {len(updates['items'])} evidence-supported revisions; {len(scope['items'])} scope entries")


if __name__ == '__main__':
    main()
