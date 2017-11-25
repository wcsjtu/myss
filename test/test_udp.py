# -*- coding: utf-8 -*-
import struct
import socket
import utils


CONFIG = utils.config()


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

    def cut_domain(self):
        """get domain from repsonse, return doamin 
        string and its length in protocol"""
        d = self._data
        domain_part = []
        up = 0
        i = self._offset
        while d[i] != self.DOMAIN_END:
            length = struct.unpack("!B", d[i])[0]
            if length >= 0xc0:
                if i >= self._offset:
                    self._offset += 2
                i = struct.unpack("!H", d[i:i+2])[0] -0xc000
                continue
            up = i + length + 1
            domain_part.append(d[i+1:up])
            if up >= self._offset:
                self._offset += (length + 1)
            i = up
        if up >= self._offset:
            self._offset += 1
        return ".".join(domain_part)


def encapsulation(dest_server, data):
    rsv_frag = b"\x00\x00\x00"
    hostname = dest_server[0]
    atype = utils.atyp(hostname)
    port = struct.pack("!H", dest_server[1])
    if atype == utils.IPV4:
        addr = b"\x01" + socket.inet_aton(hostname) 
    elif atype == utils.DOMAIN:
        length = len(hostname)
        addr = b"\x03" + struct.pack("!B", length) + hostname
    else:
        raise RuntimeError("ipv6 not support!")
    frame = "".join([rsv_frag, addr, port, data]) 
    return frame
    
def decapsulation(data):
    atype = struct.unpack("!B", data[3:4])[0]
    if atype == utils.IPV4:
        payload = data[10:]
    elif atype == utils.DOMAIN:
        length = struct.unpack("!B", data[4:5])[0]
        payload = data[7+length:]
    else:
        raise RuntimeError("ipv6 not support!")
    return payload


class DNSClient(object):

    DNS_HOST = ("8.8.8.8", 53)
    DNS_ID = b"\x00\x06"    # ID
    QR = b"\x01\x00" #\x01\x00

    
    def nslookup(self, hostname):
        payload = self.dns_request(hostname)
        proxy_server = (CONFIG["local_address"], CONFIG["local_port"])
        data = encapsulation(self.DNS_HOST, payload)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(data, proxy_server)
        
        socks5_response = sock.recv(65535)
        response = decapsulation(socks5_response)
        
        self.parse_response(response)


    def dns_request(self, hostname):
    
        COUNT = struct.pack("!HHHH", 1, 0, 0, 0)
        HEADER = self.DNS_ID + self.QR + COUNT

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

    def parse_response(self, data):
    
        resp = Resp(data)

        resp.cut(6)     # ID and question number
        answer_rrs = struct.unpack("!H", resp.cut(2))[0]
        authority_rrs = struct.unpack("!H", resp.cut(2))
        addtional_rrs = struct.unpack("!H", resp.cut(2))

        query_domain = resp.cut_domain()
        query_type = resp.cut(2)
        query_cls = resp.cut(2)

        for i in xrange(answer_rrs):
            #offset = struct.unpack("!H", resp.cut(2))[0] - 0xc000
            domain = resp.cut_domain()
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
        return 

if __name__ == "__main__":

    dns_client = DNSClient()

    hostlist = ["www.google.com.hk", "www.youtube.com", "www.facebook.com",
                "www.amazon.com"]

    cn = [ "www.jd.com", "www.baidu.com", "www.163.com", "cn.bing.com",]

    for h in hostlist:
        dns_client.nslookup(h)

    for h in cn:
        dns_client.nslookup(h)