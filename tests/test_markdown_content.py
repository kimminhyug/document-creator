import tempfile
import unittest
from pathlib import Path

from md_build import document_blocks, readable_references


class MarkdownContentTests(unittest.TestCase):
    def test_tilde_and_long_fences_preserve_literal_headings(self):
        from md_contract import blocks
        result = document_blocks('## 내용\n\n~~~json\n### Literal\n```\n~~~\n\n### Real\n', Path('.'), Path('.'))
        self.assertEqual(result[0], {'type':'code', 'text':'### Literal\n```'})
        self.assertEqual(result[1]['text'], 'Real')
        with self.assertRaises(ValueError):blocks('~~~~\ntext\n~~~')

    def test_cross_document_reference_uses_title_and_preserves_examples(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); (root/'target.md').write_text('target')
            source = '[필터](target.md) 및 [접속](https://example.test/path?q=1&x=2)'
            items = [{'type':'paragraph','text':source},{'type':'code','text':source}]
            readable_references(items,root,root,{root/'target.md':'사용자 매뉴얼 — 조회 조건'})
            self.assertEqual(items[0]['text'],'필터 (사용자 매뉴얼 — 조회 조건) 및 접속 (https://example.test/path?q=1&x=2)')
            self.assertEqual(items[1]['text'],source)
            with self.assertRaises(ValueError):
                readable_references([{'type':'paragraph','text':'[bad](https://'+'user:password@example.test)'}],root,root,{})

    def test_web_links_are_escaped_and_credentials_are_not_clickable(self):
        from inline_links import safe_url_markup
        actual = safe_url_markup('<script> https://example.test/?a=1&b=2.', ['https://example.test/?a=1&b=2'])
        self.assertIn('&lt;script&gt;',actual)
        self.assertIn('href="https://example.test/?a=1&amp;b=2"',actual)
        self.assertNotIn('<a ',safe_url_markup('https://'+'user:password@example.test'))

    def test_url_particles_and_host_placeholders_do_not_create_links(self):
        from inline_links import url_parts, validate_web_links
        address='http://127.0.0.1:8766'
        value=address+'이며 Origin은 http://와 Host를 조합한다. http://Host가 예시다.'
        parts=list(url_parts(value,[address]))
        self.assertEqual([url for _,url in parts if url],[address])
        self.assertEqual(''.join(label for label,_ in parts),value)
        self.assertFalse(any(url for _,url in url_parts(value)))
        with self.assertRaises(ValueError):validate_web_links([address+'이며'])

    def test_source_container_is_hidden_without_losing_nested_content_or_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = document_blocks('# Section\n\n## 내용\n\n### First\n\nText\n\n#### Second\n\n```markdown\n## 내용\n### Literal\n```\n\n## 관련 참조\n\nActual reference\n', root, root)
        self.assertEqual([b['text'] for b in result if b['type'] == 'heading'], ['First', 'Second', '관련 참조'])
        self.assertEqual([b['level'] for b in result if b['type'] == 'heading'], [2, 3, 2])
        self.assertEqual(next(b['text'] for b in result if b['type'] == 'code'), '## 내용\n### Literal')
        self.assertEqual([b['text'] for b in result if b['type'] == 'paragraph'], ['Text', 'Actual reference'])


if __name__ == '__main__':
    unittest.main()
