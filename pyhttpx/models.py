import gzip
import json
from collections import OrderedDict,defaultdict

import brotli

from urllib.parse import urlparse,urlencode,quote,unquote


def encodeURI(url):
    url = unquote(url)
    return quote(url,safe='!@#$&*()=:/;?+\'"')

class Request(object):
    def __init__(self,
                 method=None, url=None, headers=None, data=None,timeout=None,
                 params=None, auth=None, cookies=None,json=None,proxies=None,
                 allow_redirects=None,proxy_auth=None
                 ):
        # Default empty dicts for dict params.
        data = [] if data is None else data
        headers = {} if headers is None else headers
        params = {} if params is None else params

        self.method = method
        self.url = url
        self.headers = headers
        self.data = data
        self.json = json
        self.params = params
        self.auth = auth
        self.cookies = cookies
        self.parse_url = urlparse(url)
        self.timeout = timeout
        self.proxies = proxies
        self.proxy_auth = proxy_auth
        self.allow_redirects = allow_redirects
        self.host = self.parse_url.netloc
        self.port = 443

        if ':' in self.host:
            self.host,self.port = self.host.split(':',1)

        self.scheme = self.parse_url.scheme
        self.pre_path = self.parse_url.path or '/'

        self.prep_params = self.parse_url.query
        if self.prep_params:
            for i in self.prep_params.split('&'):
                k, v = i.split('=', 1)
                self.params[k] = v

        #url不编码字符

        self.path = self.pre_path
        if self.params:

            path = self.pre_path + '?' + '&'.join(['{}={}'.format(k,v) for k,v in self.params.items()])
            self.path = encodeURI(path)




    def __repr__(self):
        template = '<Request {method}>'
        return  template.format(method=self.method )



class Response(object):
    def __init__(self):

        self.plaintext_buffer = b''
        self.headers = {}
        self.body = b''
        self.content_length = 0
        self.encoding = 'utf-8'
        self.status_code = None
        #chunked
        self.transfer_encoding = 'chunked'
        self.read_ended = False
        self._content = b''
        self.cookies = {}

    def handle_headers(self, header_buffer):
        buffer = header_buffer.decode('latin1').split('\r\n')
        headers = defaultdict(list)

        protocol_raw,headers_raw = buffer[0],buffer[1:]
        self.status_code = int(protocol_raw.split(' ')[1])

        for head in headers_raw:
            k,v = head.split(': ', 1)
            k,v = k.lower().strip(),v.strip()
            if k == 'set-cookie':
                headers[k].append(v)
            else:
                headers[k] = v

        return headers

    def flush(self, buffer):
        self.plaintext_buffer += buffer
        if not self.headers and b'\r\n\r\n' in self.plaintext_buffer:
            header_buffer,self.plaintext_buffer = self.plaintext_buffer.split(b'\r\n\r\n', 1)
            self.headers = self.handle_headers(header_buffer)

            if self.headers.get('content-length'):
                self.content_length = int(self.headers.get('content-length', 0))
            else:
                self.content_length = None


        if self.headers:
            if self.transfer_encoding == self.headers.get('transfer-encoding'):
                #chunked
                if self.plaintext_buffer.endswith(b'0\r\n\r\n'):
                    self.body = self.plaintext_buffer
                    self.read_ended = True

            else:

                if self.content_length:
                    if self.content_length <= len(self.plaintext_buffer):
                        self.body = self.plaintext_buffer[:self.content_length]
                        self.read_ended = True
                        return
                else:
                    self.body = self.plaintext_buffer[:]

    @property
    def content(self):
        if self._content:
            return self._content
        else:
            if self.headers.get('transfer-encoding') == self.transfer_encoding :
                str_chunks = self.body
                html = b''
                m = memoryview(str_chunks)
                right = 0
                left = 0
                while len(str_chunks) > right:
                    index = str_chunks.index(b'\r\n', right)
                    right = index
                    l = int(m[left:right].tobytes(), 16)
                    html += m[right + 2:right + 2 + l]
                    right = right + 2 + l + 2
                    left = right

                self._content = html
            else:
                self._content = self.body

        content_encoding =  self.headers.get('content-encoding')
        if content_encoding == 'gzip':
            self._content = gzip.decompress(self._content)

        elif content_encoding == 'br':

            self._content = brotli.decompress(self._content)

        else:
            self._content = self._content
        return self._content

    @property
    def text(self):
        return self.content.decode(encoding=self.encoding)

    @property
    def json(self):
        return json.loads(self.text)

    def __repr__(self):
        template = '<Response status_code={status_code}>'
        return  template.format(status_code=self.status_code)

