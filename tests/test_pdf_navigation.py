import copy
import re
import tempfile
import unittest
from pathlib import Path

import reportlab
from pypdf import PdfReader
from docx import Document
import creator
from output_adapters import render_html, version_text


class PdfNavigationTests(unittest.TestCase):
    def setUp(self):
        self.theme = creator.read_json(creator.ROOT / 'themes/blue-office.json')
        self.theme['cover']['version_label'] = 'Revision'
        self.theme['copyright'].update(title='Copyright', text='{organization} test document')
        self.theme['contents']['title'] = 'Contents'
        self.theme['ending'].update(title='Contact', text='{contact}')
        self.project = dict(name='Product', organization='Company', contact='Team', classification='Test')
        fontdir = Path(reportlab.__file__).parent / 'fonts'
        self.runtime = dict(font_regular=str(fontdir / 'Vera.ttf'), font_bold=str(fontdir / 'VeraBd.ttf'))
        self.content = dict(title='Navigation test', summary='Pagination regression', version='1.0', sections=[])

    def section(self, title, count):
        return dict(title=title, status='confirmed', blocks=[dict(type='paragraph', text=f'{title} body {n:03d}') for n in range(count)])

    def test_toc_links_and_page_numbers_match_every_destination(self):
        self.content['sections'] = [self.section(f'Section {n:02d} & details', 10) for n in range(25)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'out.pdf'
            creator.render_pdf(path, self.content, self.project, self.theme, self.runtime)
            pdf = PdfReader(path)
            self.assertEqual(len(pdf.outline), 25)
            links = [a.get_object() for page in pdf.pages for a in page.get('/Annots', []) if a.get_object().get('/Subtype') == '/Link']
            self.assertEqual(len(links), 50)  # Each title and page number is clickable.
            toc_text = '\n'.join(p.extract_text() for p in pdf.pages[2:4])
            for outline in pdf.outline:
                page_index = pdf.get_destination_page_number(outline)
                self.assertIn(outline.title, pdf.pages[page_index].extract_text())
                self.assertIn(outline.title, toc_text)
                self.assertRegex(toc_text, rf'\b{page_index + 1}\n{re.escape(outline.title)}\n')
                targets = [a['/Dest'] for a in links if a['/Dest'][0] == pdf.pages[page_index].indirect_reference and a['/Dest'][3] == outline['/Top']]
                self.assertEqual(len(targets), 2)
                self.assertTrue(all(float(dest[3]) <= float(pdf.pages[page_index].mediabox.top) for dest in targets))
            self.assertIn('Revision 1.0', pdf.pages[0].extract_text())

    def test_long_sections_split_without_orphan_headings_and_short_sections_stay_together(self):
        self.content['sections'] = [self.section(f'Long{n}', 40) for n in range(6)] + [self.section('Short', 5)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'out.pdf'
            creator.render_pdf(path, self.content, self.project, self.theme, self.runtime)
            pdf = PdfReader(path)
            texts = [page.extract_text() for page in pdf.pages]
            for index, outline in enumerate(pdf.outline):
                start = pdf.get_destination_page_number(outline)
                title = self.content['sections'][index]['title']
                self.assertIn(title + ' body 000', texts[start], 'Heading must stay with first body paragraph')
                if title == 'Short':
                    self.assertIn('Short body 004', texts[start])
                else:
                    self.assertNotIn(title + ' body 039', texts[start])
                    self.assertEqual(sum(text.count(title + ' body 039') for text in texts), 1)

    def test_spacing_and_version_label_propagate_to_docx_html(self):
        self.content['sections'] = [self.section('Overview', 1)]
        self.theme['styles']['heading_1'].update(space_before_pt=23, space_after_pt=11)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'out.docx'
            creator.render_docx(path, self.content, self.project, self.theme)
            doc = Document(path)
            self.assertEqual(doc.styles['Heading 1'].paragraph_format.space_before.pt, 23)
            self.assertEqual(doc.styles['Heading 1'].paragraph_format.space_after.pt, 11)
            self.assertTrue(any('Revision 1.0' in p.text for p in doc.paragraphs))
            path = Path(tmp) / 'out.html'
            render_html(path, self.content, self.project, self.theme)
            self.assertIn('margin-top:23pt;margin-bottom:11pt', path.read_text('utf8'))
            self.assertIn('Revision 1.0', path.read_text('utf8'))
        self.theme['cover']['version_label'] = ''
        self.assertEqual(version_text(self.content, self.theme), '1.0')

    def test_layout_and_spacing_boundaries_are_validated(self):
        for value in [-1, 121, True, '85']:
            theme = copy.deepcopy(self.theme)
            theme['layout']['keep_short_sections_max_height_mm'] = value
            with self.assertRaises(ValueError): creator.validate_theme(theme)
        for value in [-1, 101, True, '9']:
            theme = copy.deepcopy(self.theme)
            theme['styles']['body'] = {'space_after_pt': value}
            with self.assertRaises(ValueError): creator.validate_theme(theme)
        self.theme['layout']['keep_short_sections_max_height_mm'] = 0
        self.assertTrue(creator.validate_theme(self.theme) is None)

    def test_unsupported_glyph_fails_instead_of_publishing_blank_text(self):
        self.content['sections'] = [dict(title='Unsupported', status='confirmed', blocks=[dict(type='paragraph', text='missing: \U0001f600')])]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'out.pdf'
            with self.assertRaisesRegex(ValueError, 'U\\+1F600'):
                creator.render_pdf(path, self.content, self.project, self.theme, self.runtime)
            self.assertFalse(path.exists())

    def test_minus_fallback_preserves_math_in_body_table_title_and_header(self):
        # Malgun lacks U+2212. Use that actual configured face when available.
        runtime_path = creator.ROOT / '.local/runtime.json'
        if not runtime_path.exists():
            self.skipTest('Configured Korean font unavailable')
        runtime = creator.read_json(runtime_path)
        self.content.update(title='End − Start', sections=[dict(title='Difference − result', status='confirmed', blocks=[
            dict(type='paragraph', text='End−Start × 100 ÷ 2 문서'),
            dict(type='table', headers=['Variable', 'Formula'], rows=[['Period', 'end_at−start_at']]),
        ])])
        self.theme['header']['left'] = 'Header − check'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'out.pdf'
            creator.render_pdf(path, self.content, self.project, self.theme, runtime)
            pdf = PdfReader(path)
            extracted = '\n'.join(page.extract_text() for page in pdf.pages)
            for text in ['End − Start', 'Difference − result', 'End−Start × 100 ÷ 2 문서', 'end_at−start_at', 'Header − check']:
                self.assertIn(text, extracted)
            self.assertNotIn('\x00', extracted)
            self.assertTrue(any('BitstreamVera' in str(font.get_object().get('/BaseFont')) for page in pdf.pages for font in page['/Resources']['/Font'].get_object().values()))

    def test_table_words_and_times_do_not_leave_single_character_lines(self):
        self.content['sections'] = [dict(title='Data', status='confirmed', blocks=[dict(type='table',
            headers=['Object', 'Type', 'Meaning', 'Count', 'Quality'], rows=[
                ['equipment_state_history', 'Table', 'State history', '26', 'complete'],
                ['expected_availability', 'numeric', 'Percent', '100', 'complete'],
                ['EQ-001 07:00~09:00', 'Period', 'Running time', '3600', 'complete'],
            ])])]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'out.pdf'
            creator.render_pdf(path, self.content, self.project, self.theme, self.runtime)
            pdf = PdfReader(path)
            body = '\n'.join(page.extract_text() for page in pdf.pages[3:-1])
            self.assertIn('equipment_state_history', body)
            self.assertIn('expected_availability', body)
            self.assertIn('07:00~09:00', body)
            self.assertFalse(any(line in ['y', '0'] for line in body.splitlines()))

    def test_new_layout_tokens_reject_invalid_types_and_values(self):
        for value in [None, 1, 'true']:
            theme = copy.deepcopy(self.theme)
            theme['layout']['keep_title_words'] = value
            with self.assertRaises(ValueError): creator.validate_theme(theme)
        for value in [None, True, 'automatic', 5]:
            theme = copy.deepcopy(self.theme)
            theme.setdefault('table', {})['column_width_mode'] = value
            with self.assertRaises(ValueError): creator.validate_theme(theme)

    def test_wrapped_url_keeps_the_original_click_destination(self):
        address = 'https://example.org/long_identifier_name/another_path?first=1&second=2'
        self.content['web_links'] = [address]
        self.theme['table']['column_width_mode'] = 'equal'
        self.content['sections'] = [dict(title='Links', status='confirmed', blocks=[dict(type='table',
            headers=['Name', 'Reference', 'Value', 'Status'], rows=[['Example', address, '42', 'Ready']])])]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'out.pdf'
            creator.render_pdf(path, self.content, self.project, self.theme, self.runtime)
            pdf = PdfReader(path)
            targets = [a.get_object().get('/A', {}).get('/URI') for page in pdf.pages for a in page.get('/Annots', [])]
            self.assertIn(address, targets)
            self.assertTrue(all(target in [None, address] for target in targets))


if __name__ == '__main__':
    unittest.main()
