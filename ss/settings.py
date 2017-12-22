# -*- coding: utf-8 -*-

from threading import RLock

class Settings(object):
    """
    command-line parameters parsed by `Command` will 
    stored in instance.
    """
    DEFAULT_TIMEOUT = 300

    _LOCK = RLock()

    def __init__(self):
        self.timeout = self.DEFAULT_TIMEOUT

    def __getitem__(self, name):
        return self.__dict__[name]

    def __setitem__(self, name, val):
        with self._LOCK:
            self.__dict__[name] = val
    
    def get(self, name, default=None):
        return self.__dict__.get(name, default)

    def update(self, config):
        with self._LOCK:
            self.__dict__.update(config)

    def dict(self):
        return {k:v for k, v in self.__dict__.items()}

settings = Settings()   

__all__ = ["settings",]