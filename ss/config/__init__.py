# -*- coding: utf-8 -*-

import platform

SYS = platform.system()

if SYS == "Windows":
    from .windows import Switcher
elif SYS == "Linux":
     from .linux import Switcher
elif SYS == "Darwin":
    pass