# -*- coding: utf-8 -*-
import os
import time
import threading
import sched
import logging
import heapq

class Watcher(object):

    def __init__(self, inteval, priority, *run_args):
        self.args = run_args
        self.inteval = inteval
        self.priority = priority

    def run(self, *args):
        raise NotImplementedError("subclass's duty")

    def fmt(self):
        return self.inteval, self.priority, self.run, self.args


class Pac(Watcher):

    LastRead = 0

    def run(self, config):
        pacfile = config["pac"]
        last = os.path.getmtime(pacfile)
        if last > self.LastRead:
            self.load(config)
        

    def load(self, config):
        from ss.core.pac import ProxyAutoConfig
        pacfile = config["pac"]
        ProxyAutoConfig.load(pacfile, **config)
        self.LastRead = time.time()

class Scheduler(sched.scheduler, threading.Thread):

    def __init__(self, **config):
        threading.Thread.__init__(self, name = "watcher")
        sched.scheduler.__init__(self, time.time, time.sleep)
        self._config = config
        self.setDaemon(True)
        self.is_running = False
        self.intval_map = dict()

    def run(self):
        logging.info("start watcher thread!")
        self.is_running = True
        q = self._queue
        delayfunc = self.delayfunc
        timefunc = self.timefunc
        pop = heapq.heappop
        while q:
            time, priority, action, argument = checked_event = q[0]
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


    def register(self, watcherobj):
        if self.is_running:
            logging.warn("cannot register task after scheduler start run!")
            return
        args = watcherobj.fmt()
        self.enter(*args)
        self.intval_map[args[2]] = args[0]
        logging.info("register task %s" % watcherobj.__class__.__name__)




    