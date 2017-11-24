# -*- coding: utf-8 -*-
import struct
import socket


"""
DNS frame

+---------------------+
|        Header       | 报文头
+---------------------+
|       Question      | 查询的问题
+---------------------+
|        Answer       | 应答
+---------------------+
|      Authority      | 授权应答
+---------------------+
|      Additional     | 附加信息
+---------------------+

HEADER structure

 0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
| ID                                            |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|QR| Opcode    |AA|TC|RD|RA| Z      | RCODE     |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
| QDCOUNT                                       |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
| ANCOUNT                                       |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
| NSCOUNT                                       |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
| ARCOUNT                                       |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

Question structure

 0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                                               |
|                     QNAME                     |
|                                               |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                     QTYPE                     |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
|                     QCLASS                    |
+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

"""


DNS_ID = b"\x00\x06"    # ID
QR = b"\x01\x00" #\x01\x00

DNS_HOST = ("8.8.8.8", 53)


class Resp(object):

    DOMAIN_END = b"\x00"

    def __init__(self, d):
        self._offset = 0
        self._data = d
        
    def cut(self, i):
        up = self._offset + i
        t = self._data[self._offset:up]
        self._offset = up
        return t

    def __getitem__(self, i):
        return self._data[i]

    def cut_domain(self, offset=0):
        """get domain from repsonse, return doamin 
        string and its length in protocol"""
        d = self._data
        domain_part = []
        i = offset or self._offset
        while d[i] != self.DOMAIN_END:
            length = struct.unpack("!B", d[i])[0]
            if length >= 0xc0:
                i = struct.unpack("!H", d[i:i+2])[0] -0xc000
                if not offset:
                    self._offset += 2
                continue
            up = i + length + 1
            domain_part.append(d[i+1:up])
            if up > self._offset:
                self._offset += (length + 1)
            i = up
        if up >= self._offset:
            self._offset += 1
        return ".".join(domain_part)


def dns_request(hostname):
    
    COUNT = struct.pack("!HHHH", 1, 0, 0, 0)
    HEADER = DNS_ID + QR + COUNT

    parts = hostname.split(".")
    qname = []
    for p in parts:
        qname += [struct.pack("!B", len(p)), p]
    qname = ''.join(qname) + b"\x00"
    QTYPE = b"\x00\x01"
    QCLASS = b"\x00\x01"
    question = qname + QTYPE + QCLASS

    r = HEADER + question
    return r


def parse_response(data):
    
    resp = Resp(data)

    resp.cut(6)     # ID and question number
    answer_rrs = struct.unpack("!H", resp.cut(2))[0]
    authority_rrs = struct.unpack("!H", resp.cut(2))
    addtional_rrs = struct.unpack("!H", resp.cut(2))

    query_domain = resp.cut_domain()
    query_type = resp.cut(2)
    query_cls = resp.cut(2)

    for i in xrange(answer_rrs):
        offset = struct.unpack("!H", resp.cut(2))[0] - 0xc000
        domain = resp.cut_domain(offset)
        type = resp.cut(2)
        cls = resp.cut(2)
        ttl = resp.cut(4)
        data_length = struct.unpack("!H", resp.cut(2))[0]
        if type == b'\x00\x01':     # ip
            ip = socket.inet_ntoa(resp.cut(data_length))
            print("%s : %s" % (domain, ip) )
        elif type == b'\x00\x05':   # cname
            cname = resp.cut_domain()
            print("%s : %s" % (domain, cname) )
    print ""
    print "========done========"
    return

def nslookup(hostname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(dns_request(hostname), DNS_HOST)
    parse_response(s.recv(4096))

if __name__ == "__main__":

    try:
        import fire
        fire.Fire(nslookup)
    except ImportError:
        import sys
        hostname = sys.argv[1]
        nslookup(hostname)

