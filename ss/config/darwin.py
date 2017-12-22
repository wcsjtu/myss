# -*- coding: utf-8 -*-
import logging
import os
from ss.core.pac import ProxyAutoConfig
from ss.wrapper import onexit
from ss.settings import settings

class Switcher(object):

    MODE = (MODE_OFF, MODE_PAC, MODE_GLB) = (0, 1, 2)

    def shift(self, mode):
        if mode not in self.MODE:
            logging.warn("invalid proxy mode %s" % mode)
            return
        eth = settings.get("ethname", "eth0")
        if mode == self.MODE_OFF:
            cmd = "\n".join([
                "networksetup -setwebproxystate %s off" % eth,
                "networksetup -setautoproxystate %s off" % eth,
                "networksetup -setsocksfirewallproxystate %s off" % eth,
                "networksetup -setsecurewebproxystate %s off" % eth,
            ])
            logging.warn("set proxy mode to `off`")
        elif mode == self.MODE_PAC:
            host = "http://%(local_address)s:%(local_port)d" % settings
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
                eth, settings["local_address"], settings["local_port"]
            )
            cmd = "\n".join([
                socks5, 
                "networksetup -setwebproxystate %s off" % eth,
                "networksetup -setautoproxystate %s off" % eth,
                "networksetup -setsecurewebproxystate %s off" % eth,
            ])
        os.system(cmd)

    def update_pac(self):
        if settings.get("proxy_mode", "off") != "pac":
            return
        host = "http://%(local_address)s:%(local_port)d" % settings
        url = host + ProxyAutoConfig.URI
        logging.info("pac url: %s" % url)
        ethname = settings.get("ethname", "eth0")
        cmd = "networksetup -setautoproxyurl %s %s" % (ethname, url)
        os.system(cmd)

@onexit
def on_exit():
    logging.info("revert intenet settings.")
    Switcher().shift(Switcher.MODE_OFF)

