# -*- coding: utf-8 -*-
import logging
from ss.core.pac import ProxyAutoConfig
from ss.wrapper import onexit
from ss.settings import settings

class Switcher(object):

    MODE = (MODE_OFF, MODE_PAC, MODE_GLB) = (0, 1, 2)

    def shift(self, mode):
        pass

    def update_pac(self):
        pass


@onexit
def on_exit():
    logging.info("revert intenet settings.")
    Switcher().shift(0)
