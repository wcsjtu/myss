# -*- coding: utf-8 -*-
import logging
from ss.core.pac import ProxyAutoConfig
from ss.wrapper import onexit


class Switcher(object):

    def shift(self, mode, **config):
        pass

    def update_pac(self, **config):
        pass


@onexit
def on_exit():
    logging.info("revert intenet settings.")
    Switcher().shift(0)
