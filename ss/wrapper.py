# -*- coding: utf-8 -*-
import sys
import functools
import logging
import signal
import threading
onexit_callbacks = []

onstart_callbacks = []

def onstart(func):
    onstart_callbacks.append(func)
    return func

def onexit(func):
    onexit_callbacks.append(func)
    return func

def exec_exitfuncs(s, _):
    logging.warn('received SIGQUIT, doing graceful shutting down..')
    for func in onexit_callbacks:
        func()
    sys.exit(0)

def exec_startfuncs(s, _):
    
    for func in onstart_callbacks:
        func()
    logging.info('all on start callbacks exec successfully')

def register(signals, func):
    if not isinstance(threading.current_thread(), threading._MainThread):
        logging.warn("signal only works in main thread, skip register signal")
        return
    for s in signals:
        sign = getattr(signal, s, None)
        if sign:
            signal.signal(sign, func)