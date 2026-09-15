import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from openpyxl import load_workbook
from docx import Document
import creator
from output_adapters import render_html, render_xlsx

class OutputTests(unittest.TestCase):
    def setUp(self):
        self.content=creator.read_json(creator.ROOT/'examples/demo/content/table-spec.json')
        self.project=creator.read_json(creator.ROOT/'examples/demo/content/project.json')
        self.theme=creator.read_json(creator.ROOT/'themes/blue-office.json')
        self.theme['copyright']={'enabled':True,'title':'저작권 안내','text':'Copyright {organization}'}
        self.theme['styles']={'heading_2':{'size_pt':19,'bold':False},'table_header':{'size_pt':13,'bold':False}}
        self.content['sections'][0]['blocks'].extend([{'type':'heading','level':2,'text':'상세 설명'}, {'type':'paragraph','text':'<script>alert(1)</script>'}, {'type':'table','headers':['값'],'rows':[['=HYPERLINK("https://example.com")'],['+1'],['@SUM(A1)']]}])
    def test_html_escapes_and_does_not_publish_internal_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'doc.html';render_html(path,self.content,self.project,self.theme);data=path.read_text('utf8')
            self.assertIn('&lt;script&gt;',data);self.assertNotIn('<script>',data);self.assertIn('Content-Security-Policy',data)
            self.assertIn('저작권 안내',data)
            for source in self.content['sources']:self.assertNotIn(source['locator'],data);self.assertNotIn(source['id'],data)
            self.assertNotIn(self.content['id'],data)
    def test_xlsx_formula_strings_and_header_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'doc.xlsx';render_xlsx(path,self.content,self.project,self.theme);wb=load_workbook(path)
            cells=[c for ws in wb for row in ws for c in row if c.value is not None]
            for cell in cells:self.assertNotEqual(cell.data_type,'f')
            header=next(c for c in cells if c.value=='값');self.assertEqual(header.font.sz,13);self.assertFalse(header.font.bold)
            self.assertEqual(header.fill.fgColor.rgb[-6:],self.theme['colors']['table_fill'][1:])
            values='\n'.join(str(c.value) for c in cells)
            self.assertNotIn(self.content['sources'][0]['id'],values);self.assertIn('=HYPERLINK',values)
            wb.close()
    def test_docx_styles_and_no_internal_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'doc.docx';creator.render_docx(path,self.content,self.project,self.theme);doc=Document(path)
            self.assertEqual(doc.styles['Heading 2'].font.size.pt,19);self.assertFalse(doc.styles['Heading 2'].font.bold)
            with ZipFile(path) as z:data=z.read('word/document.xml').decode()
            self.assertIn('저작권 안내',data);self.assertNotIn(self.content['id'],data)
            for source in self.content['sources']:self.assertNotIn(source['id'],data);self.assertNotIn(source['locator'],data)
    def test_local_image_embedded_without_local_path(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'private-image.png';Image.new('RGB',(30,20),'blue').save(source)
            self.content['sections'][0]['blocks'].append({'type':'image','path':str(source),'alt':'Overview'})
            path=Path(tmp)/'doc.html';render_html(path,self.content,self.project,self.theme)
            html=path.read_text('utf8');self.assertIn('data:image/png;base64,',html);self.assertNotIn(str(source),html)
            xlsx=Path(tmp)/'doc.xlsx';render_xlsx(xlsx,self.content,self.project,self.theme)
            with ZipFile(xlsx) as z:self.assertIn('xl/media/image1.png',z.namelist())

    def test_invalid_css_and_public_url_rejected(self):
        self.theme['styles']['body']={'font_family':'</style><script>'}
        with self.assertRaises(ValueError):creator.validate_theme(self.theme)
        from output_adapters import public_references
        with self.assertRaises(ValueError):public_references({'public_references':[{'title':'bad','url':'javascript:alert(1)'}]})
    def test_build_html_xlsx_atomic_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=creator.build(creator.ROOT/'examples/demo/content/table-spec.json',creator.ROOT/'templates/table_spec.json',creator.ROOT/'examples/demo/content/project.json',creator.ROOT/'themes/blue-office.json',None,tmp,['html','xlsx'])
            manifest=creator.read_json(out/'manifest.json');self.assertEqual(set(manifest['outputs']),{'document.html','document.xlsx'})

if __name__=='__main__': unittest.main()
