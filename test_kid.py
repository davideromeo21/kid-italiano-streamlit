import io
import unittest
import zipfile
from unittest.mock import patch
from kid_core import valid_isin, parse_isins, document_date, kid_links, resolve, make_zip, public_url

class Checks(unittest.TestCase):
    def test_isin(self):
        self.assertTrue(valid_isin('IE00B4L5Y983'))
        self.assertFalse(valid_isin('IE00B4L5Y984'))
        self.assertEqual(parse_isins('ISIN\nIE00B4L5Y983;IE00B4L5Y983'), ['IE00B4L5Y983'])
    def test_dates(self):
        self.assertEqual(document_date('Il presente documento è datato 29/09/2026.'), '2026-09-29')
        self.assertEqual(document_date('Le presenti informazioni fondamentali sono precise a far data il 16.02.2026.'), '2026-02-16')
        self.assertEqual(document_date('Data di produzione: 31/02/2025'), '')
        self.assertEqual(document_date('Scadenza del fondo: 31/12/2030'), '')
    def test_links(self):
        links=kid_links('<a href="https://example.com/PRP_IT_it_X.pdf">KID (IT)</a><a href="https://example.com/MR.pdf">Scheda</a><a href="https://example.com/PRP_DE_de_X.pdf">KID (DE)</a>', 'https://example.com')
        self.assertEqual(links,['https://example.com/PRP_IT_it_X.pdf'])
    def test_safe_url(self):
        for u in ['http://example.com','https://127.0.0.1','https://localhost','https://foo.local','https://user:pass@example.com']:
            with self.assertRaises(ValueError): public_url(u,False)
    def test_failure(self):
        with patch('kid_core.download',side_effect=ValueError('HTTP 403')):
            r=resolve('IE00B4L5Y983')
        self.assertEqual(r['stato'],'Recupero non riuscito')
        self.assertIsNone(r['pdf'])
        self.assertTrue(all(d['esito']=='HTTP 403' for d in r['diagnostica']))
    def test_zip(self):
        pdf=b'%PDF-test';r={'isin':'IE00B4L5Y983','stato':'Test','data_documento':'2026-09-03','pdf':pdf}
        with zipfile.ZipFile(io.BytesIO(make_zip([r]))) as z:
            self.assertIn('report.csv',z.namelist())
            self.assertEqual(z.read('IE00B4L5Y983_KID_IT_2026-09-03.pdf'),pdf)
if __name__=='__main__': unittest.main()
