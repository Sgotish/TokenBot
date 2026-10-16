"""No redirects, no credential logging, no automatic retry of ambiguous model calls."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

class Client:
    def __init__(self,base_url,key,timeout=120):
        url=urllib.parse.urlsplit(base_url)
        if url.username or url.password or url.query or url.fragment:
            raise ValueError('Base URL must not contain credentials, query, or fragment')
        if url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('localhost','127.0.0.1','::1')):
            raise ValueError('HTTPS required except loopback')
        if not key: raise ValueError('Set TOKENBOT_API_KEY')
        self.base=base_url.rstrip('/');self.key=key;self.timeout=timeout
        self.opener=urllib.request.build_opener(NoRedirect())

    def request(self,method,path,body=None,content_type='application/json'):
        if not path.startswith('/') or '..' in path or '?' in path or '#' in path:
            raise ValueError('Invalid API path')
        if body is not None and not isinstance(body,bytes): body=json.dumps(body).encode()
        req=urllib.request.Request(self.base+path,data=body,method=method,headers={
            'Authorization':'Bearer '+self.key,'Content-Type':content_type,'Accept':'application/json'})
        try:
            with self.opener.open(req,timeout=self.timeout) as r:
                return r.status,dict(r.headers),r.read()
        except urllib.error.HTTPError as e:
            return e.code,dict(e.headers),e.read()
        except (urllib.error.URLError,TimeoutError,OSError):
            # Provider may already have accepted and billed this request.
            return 0,{},b''

    @classmethod
    def from_env(cls):
        return cls(os.environ.get('TOKENBOT_BASE_URL','http://127.0.0.1:8180/v1'),os.environ.get('TOKENBOT_API_KEY',''))
