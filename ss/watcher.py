# -*- coding: utf-8 -*-
import os
import time
import threading
import sched
import logging
import heapq
import sys
from ss.config import Switcher
from ss.settings import settings

def add_metaclass(metaclass):
    """Class decorator for creating a class with a metaclass."""
    def wrapper(cls):
        orig_vars = cls.__dict__.copy()
        slots = orig_vars.get('__slots__')
        if slots is not None:
            if isinstance(slots, str):
                slots = [slots]
            for slots_var in slots:
                orig_vars.pop(slots_var)
        orig_vars.pop('__dict__', None)
        orig_vars.pop('__weakref__', None)
        return metaclass(cls.__name__, cls.__bases__, orig_vars)
    return wrapper


class Scheduler(sched.scheduler, threading.Thread):

    watcher_list = []

    def __init__(self):
        threading.Thread.__init__(self, name = "watcher")
        sched.scheduler.__init__(self, time.time, time.sleep)
        self.setDaemon(True)
        self.is_running = False
        self.intval_map = dict()
        self.add_to_loop()

    def run(self):
        logging.info("start watcher thread!")
        self.is_running = True
        q = self._queue
        delayfunc = self.delayfunc
        timefunc = self.timefunc
        pop = heapq.heappop
        while q:
            checked_event = q[0]
            time, priority, action, argument = checked_event[:4]
            now = timefunc()
            if now < time:
                delayfunc(time - now)
            else:
                event = pop(q)
                # Verify that the event was not removed or altered
                # by another thread after we last looked at q[0].
                if event is checked_event:
                    bt = timefunc()
                    try:
                        action(*argument)
                        delayfunc(0)   # Let other threads run
                    except Exception as e:
                        logging.warn(
                            "occur error when excute watcher %s: %s" % (action.func_name, e),
                            exc_info=True)
                        continue
                    delta = timefunc() - bt # time cost in exec action
                    self.enter(self.intval_map[action]-delta,
                        priority, action, argument)
                else:
                    heapq.heappush(q, event)

    def register(self, watchercls):
        if self.is_running:
            logging.warn("cannot register task after scheduler start run!")
            return
        args = watchercls().fmt()
        if self.check_args(args):
            self.enter(*args)
            self.intval_map[args[2]] = args[0]
            logging.info("register task %s" % watchercls.__name__)
        else:
            logging.info("skip task %s" % watchercls.__name__)

    def check_args(self, args):
        if not args:
            return False
        try:
            
            interval, priority, func, _ = args
            assert isinstance(interval, int), "inteval must be integer"
            assert isinstance(priority, int), "priority must be integer"
            assert callable(func), "func must callable!"
            return True
        except (ValueError, AssertionError) as e:
            logging.warn(e)
            return False

    def add_to_loop(self):
        for task_cls in self.watcher_list:
            self.register(task_cls)

class Register(type):

    def __new__(mcs, name, bases, attrs):
        subcls = super(Register, mcs).__new__(mcs, name, bases, attrs)
        if name != "Watcher":
            Scheduler.watcher_list.append(subcls)
        return subcls

@add_metaclass(Register)
class Watcher(object):

    def run(self, *args):
        raise NotImplementedError("subclass's duty")

    def fmt(self):
        raise NotImplementedError("subclass's duty")
        #return self.inteval, self.priority, self.run, self.args


class Pac(Watcher):

    LastRead = time.time()
    inteval = 25
    priority = 1

    def run(self):
        pacfile = settings["pac"]
        last = os.path.getmtime(pacfile)
        if last > self.LastRead:
            self.load()
        
    @classmethod
    def load(cls):
        from ss.core.pac import ProxyAutoConfig
        pacfile = settings["pac"]
        ProxyAutoConfig.load(pacfile)
        cls.LastRead = time.time()
        Switcher().update_pac()

    def fmt(self):
        return self.inteval, self.priority, self.run, tuple()


class CoinfigFile(Watcher):

    inteval = 30
    priority = 1
    last_read = time.time()
    not_support = [
                "local_http_port", "local_port", 
                "local_address", "server", "server_port"
            ]
    NOT_SUPPORT_MSG = "`%s` changed! it wouldn't takce effect util you restart this service"

    def run(self):
        from ss.cli import parse_cli
        path = settings["config_file"]
        last_mod = os.path.getmtime(path)
        if last_mod <= self.last_read:
            return
        old = settings.dict()
        try:
            parse_cli(sys.argv[1:])
            logging.info("reload config file. \r\n%s" % settings)
            self.last_read = time.time()
            for key in self.not_support:
                if settings[key] != old[key]:
                    logging.warn(self.NOT_SUPPORT_MSG % key)
            self.on_reload(old)
        except SystemExit as e:
            logging.error("config file error: %s" % e)
        
    def on_reload(self, old):
        change = lambda key: old.get(key) != settings.get(key)
        if change("pac"):
            Pac.load()
        if change("proxy_mode"):
            from ss.config import set_proxy_mode
            set_proxy_mode()

    def fmt(self):
        if not settings.get("config_file"):
            return None
        return self.inteval, self.priority, self.run, tuple()