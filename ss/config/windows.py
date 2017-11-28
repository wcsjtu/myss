# -*- coding: utf-8 -*-

"""edit Registry to shift proxy mode."""
import logging
try:
    import _winreg as winreg
except ImportError:
    import winreg

from ss.core.pac import ProxyAutoConfig
from ss.wrapper import onexit

KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


class Switcher(object):

    MODE = (MODE_OFF, MODE_PAC, MODE_GLB) = (0, 1, 2)
    PROXY_OVERRIDE = "localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;"\
    "172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;172.26.*;172.27.*;"\
    "172.28.*;172.29.*;172.30.*;172.31.*;172.32.*;192.168.*;<local>"

    def shift(self, mode, **config):
        if mode not in self.MODE:
            logging.warn("invalid proxy mode %s" % mode)
            return
        hkey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
            KEY, 0, winreg.KEY_ALL_ACCESS)
        try:
            setex = winreg.SetValueEx
            if mode == self.MODE_OFF:
                setex(hkey, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                setex(hkey, "ProxyServer", 0, winreg.REG_SZ, "")
                setex(hkey, "AutoConfigURL", 0, winreg.REG_SZ, "")
            elif mode == self.MODE_PAC:
                host = "http://%(local_address)s:%(local_port)d" % config
                url = host + ProxyAutoConfig.URI
                setex(hkey, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                setex(hkey, "ProxyServer", 0, winreg.REG_SZ, "")
                setex(hkey, "AutoConfigURL", 0, winreg.REG_SZ, url)
                setex(hkey, "ProxyOverride", 0, winreg.REG_SZ, self.PROXY_OVERRIDE) 
            else:
                setex(hkey, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                server = "%(local_address)s:%(local_port)d" % config
                setex(hkey, "ProxyServer", 0, winreg.REG_SZ, server)
        except Exception as e:
            logging.warn("fail to shift proxy mode: %s" % e)
        finally:
            hkey.Close()
        
    def update_pac(self, **config):
        hkey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
            KEY, 0, winreg.KEY_ALL_ACCESS)
        setex = winreg.SetValueEx
        try:
            host = "http://%(local_address)s:%(local_port)d" % config
            url = host + ProxyAutoConfig.URI
            setex(hkey, "AutoConfigURL", 0, winreg.REG_SZ, url)
        except Exception as e:
            logging.warn("fail to update pac url: %s" % e)
        finally:
            hkey.Close()

@onexit
def on_exit():
    logging.info("revert intenet settings.")
    Switcher().shift(0)

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