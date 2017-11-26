# -*- coding: utf-8 -*-

import logging

class ProxyAutoConfig(object):

    content = ""

    def __str__(self):
        s = "HTTP/1.1 200 OK\r\n"\
        "Server: myss\r\n"\
        "Connection: Close\r\n"\
        "Content-Type: application/x-ns-proxy-autoconfig\r\n"\
        "Content-Length: %d\r\n"\
        "\r\n"\
        "%s\r\n" % (len(self.content), self.content)
        return s

    @classmethod
    def load(cls, path):
        with open(path, "r") as f:
            cls.content = f.read()
        logging.info("reload pac file : %s" % path)


if __name__ == "__main__":

    print(str(ProxyAutoConfig()))