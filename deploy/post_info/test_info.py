"""Regression checks for the static, information-only preview."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,unittest
from html.parser import HTMLParser

HERE=Path(__file__).resolve().parent
class Tags(HTMLParser):
    def __init__(self):super().__init__();self.tags=[];self.urls=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)
        for key,value in attrs:
            if key in ['href','src']:self.urls.append(value)
            assert not key.startswith('on'),'Inline event handler is forbidden'

class InfoOnlyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='/opt/data/cache/scratch')
        self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name)/'bundle'
        run=subprocess.run([sys.executable,str(HERE/'build.py'),'--out',str(self.out)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,'Information-only builder is missing or failed: '+run.stderr[:400])

    def test_bundle_is_complete_and_hash_verified(self):
        manifest=json.loads((self.out/'manifest.json').read_text())
        expected={'index.html','terms.html','privacy.html','style.css','cat.webp'}
        self.assertEqual(set(manifest['files']),expected)
        self.assertEqual({str(p.relative_to(self.out/'public')) for p in (self.out/'public').rglob('*') if p.is_file()},expected)
        for name,meta in manifest['files'].items():
            data=(self.out/'public'/name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),meta['sha256'])

    def test_public_documents_cannot_collect_credentials(self):
        for name in ['index.html','terms.html','privacy.html']:
            html=(self.out/'public'/name).read_text();parsed=Tags();parsed.feed(html)
            self.assertFalse(set(parsed.tags)&{'script','form','input','iframe','object','embed'})
            self.assertIn('가입과 로그인은 중단되어 있습니다',html)
            self.assertIn('운영: TeemoBKK',html)
            self.assertIn('mailto:freaky0@gmail.com',parsed.urls)
            self.assertTrue(all(url.startswith(('/','mailto:freaky0@gmail.com','https://teemobkk.io/about/')) for url in parsed.urls))
            self.assertNotIn('/accounts/email/',html)
            if name!='index.html':self.assertIn('개발 검토용 초안',html)

    def test_proxy_opens_only_exact_read_only_information_paths(self):
        config=(self.out/'preview.caddy').read_text()
        for path in ['/','/accounts/policy/terms/','/accounts/policy/privacy/','/info-assets/style.css','/info-assets/cat.webp']:
            self.assertIn('path '+path+'\n',config)
        self.assertEqual(config.count('method GET HEAD'),5)
        self.assertEqual(config.count('file_server'),5)
        self.assertNotIn('reverse_proxy',config)
        self.assertNotIn('path /*',config)
        self.assertIn('form-action \'none\'',config)
        self.assertIn('frame-ancestors \'none\'',config)
        self.assertIn('503',config)

    def test_existing_bundle_is_not_overwritten(self):
        original=(self.out/'manifest.json').read_bytes()
        run=subprocess.run([sys.executable,str(HERE/'build.py'),'--out',str(self.out)],capture_output=True)
        self.assertNotEqual(run.returncode,0)
        self.assertEqual((self.out/'manifest.json').read_bytes(),original)

if __name__=='__main__':unittest.main()
