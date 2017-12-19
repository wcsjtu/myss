# -*- coding: utf-8 -*-
import logging
import os
from ss.core.pac import ProxyAutoConfig
from ss.wrapper import onexit


class Switcher(object):

    MODE = (MODE_OFF, MODE_PAC, MODE_GLB) = (0, 1, 2)

    def shift(self, mode, **config):
        if mode not in self.MODE:
            logging.warn("invalid proxy mode %s" % mode)
            return
        eth = config.get("ethname", "eth0")
        if mode == self.MODE_OFF:
            cmd = "\n".join([
                "networksetup -setwebproxystate %s off" % eth,
                "networksetup -setautoproxystate %s off" % eth,
                "networksetup -setsocksfirewallproxystate %s off" % eth,
                "networksetup -setsecurewebproxystate %s off" % eth,
            ])
            logging.warn("set proxy mode to `off`")
        elif mode == self.MODE_PAC:
            host = "http://%(local_address)s:%(local_port)d" % config
            url = host + ProxyAutoConfig.URI
            logging.info("set proxy mode to `pac`, pac url: %s" % url)
            cmd = "\n".join([
                "networksetup -setautoproxyurl %s %s" % (eth, url),
                "networksetup -setwebproxystate %s off" % eth,
                "networksetup -setsocksfirewallproxystate %s off" % eth,
                "networksetup -setsecurewebproxystate %s off" % eth,
                ])
        else:
            logging.warn("set proxy mode to `global`")
            socks5 = "networksetup -setsocksfirewallproxy %s %s %d" % (
                eth, config["local_address"], config["local_port"]
            )
            cmd = "\n".join([
                socks5, 
                "networksetup -setwebproxystate %s off" % eth,
                "networksetup -setautoproxystate %s off" % eth,
                "networksetup -setsecurewebproxystate %s off" % eth,
            ])
        os.system(cmd)

    def update_pac(self, **config):
        if config.get("proxy_mode", "off") != "pac":
            return
        host = "http://%(local_address)s:%(local_port)d" % config
        url = host + ProxyAutoConfig.URI
        logging.info("pac url: %s" % url)
        ethname = config.get("ethname", "eth0")
        cmd = "networksetup -setautoproxyurl %s %s" % (ethname, url)
        os.system(cmd)

@onexit
def on_exit():
    logging.info("revert intenet settings.")
    Switcher().shift(Switcher.MODE_OFF)

if __name__ == "__main__":

    cfg = {
        "rhost": "127.0.0.1:7410",
        "local_address": "127.0.0.1",
        "local_port": 1088,
        "local_http_port": 1089,
        "password": "123456",
        "timeout": 300,
        "method": "aes-256-cfb",
        "fast_open": False
    }
    s = Switcher()
    s.shift(0, **cfg)