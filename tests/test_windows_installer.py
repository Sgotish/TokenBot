"""Windows PowerShell 5.1 + real curl/cmd regressions; only synthetic HTTP data."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.name=='nt','Requires Windows PowerShell 5.1 and curl.exe')
class WindowsInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload=bytes(range(256))*8192
        cls.digest=hashlib.sha256(cls.payload).hexdigest()
        cls.requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                prior=sum(p==self.path for p,_ in cls.requests)
                offset=int(self.headers.get('Range','bytes=0-').split('=')[1].split('-')[0])
                cls.requests.append((self.path,offset))
                resume=offset and self.path!='/ignore'
                start=offset if resume else 0
                self.send_response(206 if resume else 200)
                self.send_header('Content-Length',str(len(cls.payload)-start))
                if resume:self.send_header('Content-Range',f'bytes {start}-{len(cls.payload)-1}/{len(cls.payload)}')
                self.end_headers()
                body=cls.payload[start:]
                if self.path=='/bad':body=b'X'+body[1:]
                if self.path in ('/drop','/restart') and prior==0:
                    self.wfile.write(body[:len(body)//2]);self.wfile.flush()
                    self.connection.shutdown(socket.SHUT_RDWR);self.connection.close()
                else:
                    try:self.wfile.write(body)
                    except (ConnectionError,OSError):pass  # curl rejects ignored Range
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=5)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'TokenBots 中文 & ! directory'
        self.root.mkdir()

    def tearDown(self):self.temp.cleanup()

    def powershell(self,script):
        path=self.root/'probe.ps1';path.write_text(script,encoding='utf-8-sig')
        return subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',str(path)],capture_output=True,timeout=60)

    def download(self,endpoint,attempts=3):
        helper=str(ROOT/'integrations/windows-codex/native-menu/get-package.ps1').replace("'","''")
        return self.powershell(f"""$ErrorActionPreference='Stop'
. '{helper}'
Get-TokenBotsPackage -Url '{self.url}/{endpoint}' -Destination (Join-Path $PSScriptRoot 'package.msix') -Sha256 '{self.digest}' -Size {len(self.payload)} -Attempts {attempts} -RetryDelay 0
""")

    def test_interrupted_response_resumes_and_verified_cache_needs_no_network(self):
        r=self.download('drop');self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace'))
        self.assertEqual((self.root/'package.msix').read_bytes(),self.payload)
        self.assertIn(('/drop',len(self.payload)//2),self.requests)
        before=len(self.requests)
        self.assertEqual(self.download('drop').returncode,0)
        self.assertEqual(len(self.requests),before)

    def test_exit_and_restart_preserve_partial(self):
        self.assertNotEqual(self.download('restart',attempts=1).returncode,0)
        self.assertEqual((self.root/'package.msix.partial').stat().st_size,len(self.payload)//2)
        self.assertFalse((self.root/'package.msix').exists())
        self.assertEqual(self.download('restart').returncode,0)
        self.assertIn(('/restart',len(self.payload)//2),self.requests)
        self.assertEqual((self.root/'package.msix').read_bytes(),self.payload)

    def test_server_ignoring_range_restarts_without_appending_full_body(self):
        (self.root/'package.msix.partial').write_bytes(self.payload[:12345])
        r=self.download('ignore');self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace'))
        self.assertIn(('/ignore',12345),self.requests)
        self.assertEqual((self.root/'package.msix').read_bytes(),self.payload)
        self.assertEqual(len(list(self.root.glob('*.no-range-*'))),1)

    def test_corrupt_download_never_becomes_installable(self):
        self.assertNotEqual(self.download('bad').returncode,0)
        self.assertFalse((self.root/'package.msix').exists())
        self.assertFalse((self.root/'package.msix.partial').exists())
        self.assertEqual(len(list(self.root.glob('*.invalid-*'))),1)

    def test_complete_partial_is_promoted_without_network(self):
        (self.root/'package.msix.partial').write_bytes(self.payload)
        before=len(self.requests)
        self.assertEqual(self.download('full').returncode,0)
        self.assertEqual(len(self.requests),before)

    def launch(self):
        env=dict(os.environ,TOKENBOTS_INSTALL_NO_PAUSE='1')
        # Keep native cmd quoting, including spaces, ampersand, ! and Unicode.
        command=f'"{env["COMSPEC"]}" /d /s /c ""{self.root / "install-native.cmd"}" -ArchivePath "{self.root / "offline file.msix"}""'
        return subprocess.run(command,cwd=Path(os.environ['SystemRoot'])/'System32',env=env,capture_output=True,timeout=30)

    def test_launcher_resolves_its_own_directory_and_passes_offline_path(self):
        shutil.copyfile(ROOT/'integrations/windows-codex/install-native.cmd',self.root/'install-native.cmd')
        native=self.root/'native-menu';native.mkdir()
        (native/'install.ps1').write_text("param([string]$ArchivePath)\n[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'called.txt'),$ArchivePath)\nexit 0\n",encoding='utf-8-sig')
        r=self.launch();self.assertEqual(r.returncode,0,r.stdout.decode(errors='replace')+r.stderr.decode(errors='replace'))
        self.assertEqual((native/'called.txt').read_text(encoding='utf-8'),str(self.root/'offline file.msix'))

    def test_missing_sibling_shows_extract_all_before_powershell(self):
        shutil.copyfile(ROOT/'integrations/windows-codex/install-native.cmd',self.root/'install-native.cmd')
        r=self.launch();self.assertEqual(r.returncode,1)
        self.assertIn(b'[INCOMPLETE_PACKAGE]',r.stdout)
        self.assertIn(b'Extract All',r.stdout)
        self.assertNotIn(b'Windows PowerShell',r.stdout)

    def test_repair_without_private_config_fails_before_download(self):
        shutil.copytree(ROOT/'integrations/windows-codex/native-menu',self.root/'native-menu')
        r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.root/'native-menu/install.ps1')],capture_output=True,timeout=30)
        self.assertNotEqual(r.returncode,0)
        self.assertIn(b'[PRIVATE_CONFIG_MISSING]',r.stderr)

if __name__=='__main__':unittest.main()
