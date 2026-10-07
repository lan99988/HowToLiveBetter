import copy
import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build', ROOT / 'scripts/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class HandbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build.read_data()
        cls.generated = build.outputs(cls.data)

    def test_complete_item_coverage_and_stable_ids(self):
        self.assertEqual(len(self.data['items']), 552)
        self.assertEqual({r['chapter'] for r in self.data['items']}, set(range(1, 33)))
        for chapter in self.data['chapters']:
            body = self.generated[chapter['file']]
            for r in self.data['items']:
                if r['chapter'] == chapter['number']:
                    self.assertIn(f'id="{r["id"]}"', body)
                    self.assertIn(r['summary'], body)
                    self.assertIn(r['original_title'], body)

    def test_embedded_data_round_trip(self):
        raw = re.search(r'<script id="handbook-data" type="application/json">(.*?)</script>', self.generated['index.html'], re.S).group(1)
        self.assertEqual(json.loads(raw), self.data)

    def test_untrusted_text_cannot_close_data_script(self):
        data = copy.deepcopy(self.data)
        payload = '</script><img src=x onerror=alert(1)> & 测试\u2028'
        data['items'][0]['original_title'] = payload
        generated = build.outputs(data)['index.html']
        static = generated.split('<script id="handbook-data"')[0]
        self.assertNotIn('<img src=x', static)
        self.assertIn(build.html.escape(payload, quote=True), static)
        raw = re.search(r'<script id="handbook-data" type="application/json">(.*?)</script>', generated, re.S).group(1)
        self.assertNotIn('</script>', raw)
        self.assertNotIn('<img', raw)
        self.assertEqual(json.loads(raw)['items'][0]['original_title'], payload)

    def test_status_is_explicit_not_emoji_substring(self):
        self.assertTrue(all(r['status'] in build.STATUS for r in self.data['items']))
        self.assertNotIn('audit_status.includes', self.generated['index.html'])
        self.assertNotIn('id="search"', self.generated['index.html'])
        for code in build.STATUS:
            self.assertEqual(self.generated['index.html'].count(f'class="status {code}"'),
                             sum(r['status'] == code for r in self.data['items']))

    def test_full_text_is_static_and_never_collapsed(self):
        page = self.generated['index.html'].split('<script id="handbook-data"')[0]
        self.assertEqual(page.count('<article class="entry"'), 552)
        self.assertEqual(page.count('<section class="chapter"'), 32)
        self.assertNotIn('<details class="entry-details"', page)
        self.assertNotIn('@@', page)
        for row in self.data['items']:
            self.assertIn(build.html.escape(row['original_title'], quote=True), page)
            self.assertIn(build.html.escape(row['summary'], quote=True), page)

    def test_no_network_runtime_assets(self):
        page = self.generated['index.html']
        self.assertNotRegex(page, r'<script\b[^>]*\bsrc=')
        self.assertNotRegex(page, r'<link\b[^>]*\bhref=')
        self.assertNotRegex(page, r'\b(fetch|XMLHttpRequest|WebSocket)\s*\(')
        self.assertNotIn('@import', page)

    def test_review_dates_and_evidence(self):
        for r in self.data['items']:
            self.assertEqual(r['last_verified'], '2026-09-20')
            if r['review_outcome'] == 'verified':
                self.assertEqual(r['verified_at'], r['checked_at'])
                self.assertTrue(r['sources'])
                self.assertTrue(r['conditions'])
            elif r['review_outcome'] == 'legacy':
                self.assertIsNone(r['checked_at'])
                self.assertIsNone(r['verified_at'])
            else:
                self.assertIsNone(r['verified_at'])

    def test_review_manifest_is_covered(self):
        scope = json.loads((ROOT / 'data/review-scope.json').read_text(encoding='utf-8'))
        candidates = scope['items'] if isinstance(scope, dict) else scope
        items = {r['id']: r for r in self.data['items']}
        for entry in candidates:
            row = items[entry['id']]
            self.assertIn(row['review_outcome'], ('verified', 'unresolved', 'contradicted'))
            self.assertTrue(row['change_reason'])
            self.assertIn(row['id'], self.generated['REVIEW_LOG.md'])

    def test_generated_files_match_source(self):
        for name, content in self.generated.items():
            self.assertEqual((ROOT / name).read_text(encoding='utf-8'), content, name)


if __name__ == '__main__':
    unittest.main()
