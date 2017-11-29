# -*- coding: utf-8 -*-
import sys
import urlparse
import urllib
import struct
import socket
import utils

HTTP_TMPL = "%(method)s %(uri)s HTTP/1.1\r\n"\
"User-Agent: Mozilla/5.0 (Windows NT 6.1; WOW64; rv:49.0) Gecko/20100101 Firefox/49.0\r\n"\
"Host: %(host)s\r\n"\
"\r\n"

HTTP_TMPL_PAYLOAD = "%(method)s %(uri)s HTTP/1.1\r\n"\
"User-Agent: Mozilla/5.0 (Windows NT 6.1; WOW64; rv:49.0) Gecko/20100101 Firefox/49.0\r\n"\
"Host: %(host)s\r\n"\
"Content-Length: %(cleng)s\r\n"\
"\r\n"\
"%(content)s\r\n"

CONFIG = utils.config()

SOCKS5_NEGO = b"\x05\x01\x00"

def socks5_request(hostname, port):
    atype = utils.atyp(hostname)
    if atype == utils.IPV4:
        req = b"\x05\x01\x00\x01%s%s" % ( socket.inet_aton(hostname), struct.pack(">H", port) )
    elif atype == utils.IPV6:
        print("don't support ipv6 yet!")
        sys.exit(1)
    else:
        l = struct.pack(">B", len(hostname))
        req = b"\x05\x01\x00\x03%s%s%s" % (l, hostname, struct.pack(">H", port))
    return req


class Socks5(object):

    def __init__(self):
        self.sock = None
        self._proxy_server = (CONFIG["local_address"], 
            int(CONFIG["local_port"]))
        
    def close(self):
        self.sock.close()
        self.sock = None
    
    def connect(self, proxy_server=None):
        if self.sock:
            return True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server = proxy_server or self._proxy_server
        self._proxy_server = server
        self.sock.connect(server)
        self.sock.send(SOCKS5_NEGO)
        response = self.sock.recv(2)
        if response == b"\x01\xff":
            self.close()
            return False
        return True

    def _http(self, method, url, payload={}):
        p = urlparse.urlsplit(url)
        hostname = p.hostname
        port = p.port or (443 if p.scheme == "https" else 80)
        uri = p.path
        payload = urllib.urlencode(payload) or p.query
        data = {"method": method, "uri": uri, "host": "%s:%s" %(hostname, port),
                "cleng": len(payload), "content": payload}
        tcp_payload = HTTP_TMPL_PAYLOAD % data if payload else HTTP_TMPL % data
        return hostname, port, tcp_payload 

    def read(self, bufsize):
        msg = self.sock.recv(bufsize)
        if not msg:
            self.close()
        return msg

    def _socks5_syn(self, hostname, port):
        req = socks5_request(hostname, port)
        self.sock.send(req)
        resp = self.sock.recv(4)
        if not resp:
            self.close()
            return
        l = struct.unpack("!BBBB", resp)
        d = ""
        if l[1] != 0:
            print("socks5 request failed!")
            self.close()
            return
        if l[-1] == 1:
            d = self.read(4+2)
        elif l[-1] == 3:
            d = self.read(1)
            bufsize = struct.unpack("!B", d)[0] + 2
            d = self.read(bufsize)
        elif l[-1] == 4:
            d = self.read(16+2)
        return d

    def get(self, url, payload={}):
        ok = self.connect()
        if not ok:
            print("connect closed by proxy server")
            return
        hostname, port, tcp_payload = self._http("GET", url, payload)
        resp = self._socks5_syn(hostname, port)
        #time.sleep(5)
        self.sock.send(tcp_payload)
        data = self.read(4096)
        print data
        self.close()
        return data
        
def main():
    urls = [
        "http://www.jd.com/",
        "http://www.baidu.com/"
    ]

    sock_client = Socks5()
    for url in urls:
        d = sock_client.get(url)
        assert "HTTP" in d
        
if __name__ == "__main__":

    main()