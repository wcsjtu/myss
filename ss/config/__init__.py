# -*- coding: utf-8 -*-

import platform
from ss.settings import settings
from ss.wrapper import onstart
SYS = platform.system()

if SYS == "Windows":
    from .windows import Switcher
elif SYS == "Linux":
     from .linux import Switcher
elif SYS == "Darwin":
    from .darwin import Switcher

@onstart
def set_proxy_mode():
    modename = settings["proxy_mode"]
    if modename == "pac":
        Switcher().shift(Switcher.MODE_PAC)
    elif modename == "global":
        Switcher().shift(Switcher.MODE_GLB)
    elif modename == "off":
        Switcher().shift(Switcher.MODE_OFF)