# -*- coding: utf-8 -*-

"""edit Registry to shift proxy mode."""
import logging
from ctypes import *
from ctypes.wintypes import *

LPWSTR = POINTER(WCHAR)
HINTERNET = LPVOID

INTERNET_PER_CONN_FLAGS = 1
INTERNET_PER_CONN_AUTOCONFIG_URL = 4
INTERNET_PER_CONN_AUTODISCOVERY_FLAGS = 5
INTERNET_OPTION_REFRESH = 37
INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_PER_CONNECTION_OPTION = 75

PROXY_TYPE_AUTO_PROXY_URL = 4
INTERNET_PER_CONN_PROXY_SERVER = 2
INTERNET_PER_CONN_PROXY_BYPASS = 3



class INTERNET_PER_CONN_OPTION(Structure):
    class Value(Union):
        _fields_ = [
            ('dwValue', DWORD),
            ('pszValue', LPWSTR),
            ('ftValue', FILETIME),
        ]

    _fields_ = [
        ('dwOption', DWORD),
        ('Value', Value),
    ]


class INTERNET_PER_CONN_OPTION_LIST(Structure):
    _fields_ = [
        ('dwSize', DWORD),
        ('pszConnection', LPWSTR),
        ('dwOptionCount', DWORD),
        ('dwOptionError', DWORD),
        ('pOptions', POINTER(INTERNET_PER_CONN_OPTION)),
    ]


from ss.core.pac import ProxyAutoConfig
from ss.wrapper import onexit


class Switcher(object):

    MODE = (MODE_OFF, MODE_PAC, MODE_GLB) = (0, 1, 2)
    PROXY_OVERRIDE = "localhost;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;"\
    "172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;172.26.*;172.27.*;"\
    "172.28.*;172.29.*;172.30.*;172.31.*;172.32.*;192.168.*;<local>"

    inte_set_opt = windll.wininet.InternetSetOptionW
    inte_set_opt.argtypes = [HINTERNET, DWORD, LPVOID, DWORD]
    inte_set_opt.restype  = BOOL

    def shift(self, mode, **config):
        if mode not in self.MODE:
            logging.warn("invalid proxy mode %s" % mode)
            return
        List = INTERNET_PER_CONN_OPTION_LIST()
        nSize = c_ulong(sizeof(INTERNET_PER_CONN_OPTION_LIST))
        try:
            if mode == self.MODE_OFF:
                logging.warn("set proxy mode to `off`")
                option_count = 2
                Option = (INTERNET_PER_CONN_OPTION * option_count)()
                Option[0].dwOption = INTERNET_PER_CONN_FLAGS
                Option[0].Value.dwValue = 1
                Option[1].dwOption = INTERNET_PER_CONN_PROXY_SERVER
                Option[1].Value.pszValue = None
            elif mode == self.MODE_PAC:
                host = "http://%(local_address)s:%(local_port)d" % config
                url = host + ProxyAutoConfig.URI
                logging.info("set proxy mode to `pac`, pac url: %s" % url)
                option_count = 3
                Option = (INTERNET_PER_CONN_OPTION * option_count)()
                Option[0].dwOption = INTERNET_PER_CONN_AUTOCONFIG_URL
                Option[0].Value.pszValue = create_unicode_buffer(url)
                Option[1].dwOption = INTERNET_PER_CONN_FLAGS
                Option[1].Value.dwValue = PROXY_TYPE_AUTO_PROXY_URL
                Option[2].dwOption = INTERNET_PER_CONN_PROXY_BYPASS
                Option[2].Value.pszValue = create_unicode_buffer(self.PROXY_OVERRIDE)
            else:
                logging.warn("set proxy mode to `global`")
                server = "%(local_address)s:%(local_http_port)d" % config
                option_count = 2
                Option = (INTERNET_PER_CONN_OPTION * option_count)()
                Option[0].dwOption = INTERNET_PER_CONN_FLAGS
                Option[0].Value.dwValue = 2
                Option[1].dwOption = INTERNET_PER_CONN_PROXY_SERVER
                Option[1].Value.pszValue = create_unicode_buffer(server)
            List.dwSize = sizeof(INTERNET_PER_CONN_OPTION_LIST)
            List.pszConnection = None
            List.dwOptionCount = option_count
            List.dwOptionError = 0
            List.pOptions = Option
            self.inte_set_opt(None, INTERNET_OPTION_PER_CONNECTION_OPTION,
                byref(List), nSize)
            self.inte_set_opt(None, INTERNET_OPTION_SETTINGS_CHANGED, None, 0)
            self.inte_set_opt(None, INTERNET_OPTION_REFRESH, None, 0)
        except Exception as e:
            logging.warn("fail to shift proxy mode: %s" % e)


    def update_pac(self, **config):
        if config.get("proxy_mode", "off") != "pac":
            return
        try:
            host = "http://%(local_address)s:%(local_port)d" % config
            url = host + ProxyAutoConfig.URI
            logging.info("pac url: %s" % url)
            List = INTERNET_PER_CONN_OPTION_LIST()
            nSize = c_ulong(sizeof(INTERNET_PER_CONN_OPTION_LIST))
            option_count = 3
            Option = (INTERNET_PER_CONN_OPTION * option_count)()
            Option[0].dwOption = INTERNET_PER_CONN_AUTOCONFIG_URL
            Option[0].Value.pszValue = create_unicode_buffer(url)
            Option[1].dwOption = INTERNET_PER_CONN_FLAGS
            Option[1].Value.dwValue = PROXY_TYPE_AUTO_PROXY_URL
            Option[2].dwOption = INTERNET_PER_CONN_PROXY_BYPASS
            Option[2].Value.pszValue = create_unicode_buffer(self.PROXY_OVERRIDE)
            List.dwSize = sizeof(INTERNET_PER_CONN_OPTION_LIST)
            List.pszConnection = None
            List.dwOptionCount = option_count
            List.dwOptionError = 0
            List.pOptions = Option
            self.inte_set_opt(None, INTERNET_OPTION_PER_CONNECTION_OPTION, 
                byref(List), nSize)
            self.inte_set_opt(None, INTERNET_OPTION_SETTINGS_CHANGED, None, 0)
            self.inte_set_opt(None, INTERNET_OPTION_REFRESH, None, 0)
        except Exception as e:
            logging.warn("fail to update pac url: %s" % e)

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