# -*- coding: utf-8 -*-
import os
import sys
import unittest
import subprocess

PWD = os.path.dirname(__file__)

import test_tcp, test_udp, test_http_tunnel

def start_services():
    def run(name):
        filename = "%s.py" % name
        filepath = os.path.join(PWD, filename)
        service = subprocess.Popen("python " + filepath, shell=False)
        print("run service ss%s" % name)
        return service

    server = run("ssserver")
    local = run("sslocl")
    return server, local

class TestMyss(unittest.TestCase):

    SERVER = None
    LOCAL = None

    @classmethod
    def setUpClass(cls):
        s, l = start_services()
        cls.SERVER = s
        cls.LOCAL = l
        print("test prepared!")

    def testTCP(self):
        test_tcp.main()

    def testUDP(self):
        test_udp.main()

    def testHTTP(self):
        test_http_tunnel.main()
    

    @classmethod
    def tearDownClass(cls):
        cls.SERVER.kill()
        cls.LOCAL.kill()
        print("all services stop!")


