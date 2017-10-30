# -*- coding: utf-8 -*-

import socket

template = "CONNECT %s:%d HTTP/1.1\r\n\r\n"

HTTP_REQUEST = "GET %s HTTP/1.1\r\nUser-Agent:python2.7\r\n\r\n"


class TunnelClient(object):

    def __init__(self, addr):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(addr)
        self.sock = sock

    def connect(self, target_addr):
        self.sock.send(template % target_addr)
        repsonse = self.sock.recv(1024)
        print repsonse
        assert "200" in repsonse

    def send(self, data):
        self.sock.send(data)
        return self.sock.recv(65535)

    def close(self):
        self.sock.close()


if __name__ == "__main__":

    tc = TunnelClient(("127.0.0.1", 1089))
    tc.connect(("www.baidu.com", 80))
    print tc.send(HTTP_REQUEST % "/")

