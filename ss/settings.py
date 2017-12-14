# -*- coding: utf-8 -*-

class Settings(object):
    """
    command-line parameters parsed by `Command` will 
    stored in instance.
    """
    DEFAULT_TIMEOUT = 300
    timeout = DEFAULT_TIMEOUT



settings = Settings()   

__all__ = ["settings",]