#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2015 clowwindy
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# from ssloop
# https://github.com/clowwindy/ssloop

from __future__ import absolute_import, division, print_function, \
    with_statement

import os
import time
import socket
import select
import errno
import logging
import threading
from collections import defaultdict
from . import utils

TIMEOUT_PRECISION = 10

class KqueueLoop(object):

    MAX_EVENTS = 1024

    def __init__(self):
        self._kqueue = select.kqueue()
        self._fds = {}

    def _control(self, fd, mode, flags):
        events = []
        if mode & IOLoop.READ:
            events.append(select.kevent(fd, select.KQ_FILTER_READ, flags))
        if mode & IOLoop.WRITE:
            events.append(select.kevent(fd, select.KQ_FILTER_WRITE, flags))
        for e in events:
            self._kqueue.control([e], 0)

    def poll(self, timeout):
        if timeout < 0:
            timeout = None  # kqueue behaviour
        events = self._kqueue.control(None, KqueueLoop.MAX_EVENTS, timeout)
        results = defaultdict(lambda: 0x00)
        for e in events:
            fd = e.ident
            if e.filter == select.KQ_FILTER_READ:
                results[fd] |= IOLoop.READ
            if e.filter == select.KQ_FILTER_WRITE:
                if e.flags & select.KQ_EV_EOF:
                    # If an asynchronous connection is refused, kqueue
                    # returns a write event with the EOF flag set.
                    # Turn this into an error for consistency with the
                    # other IOLoop implementations.
                    # Note that for read events, EOF may be returned before
                    # all data has been consumed from the socket buffer,
                    # so we only check for EOF on write events.
                    results[fd] = IOLoop.ERROR
                else:
                    results[fd] |= IOLoop.WRITE
            if e.flags & select.KQ_EV_ERROR:
                results[fd] |= IOLoop.ERROR
        return results.items()

    def register(self, fd, mode):
        self._fds[fd] = mode
        self._control(fd, mode, select.KQ_EV_ADD)

    def unregister(self, fd):
        self._control(fd, self._fds[fd], select.KQ_EV_DELETE)
        del self._fds[fd]

    def modify(self, fd, mode):
        self.unregister(fd)
        self.register(fd, mode)

    def close(self):
        self._kqueue.close()

    
class SelectLoop(object):

    def __init__(self):
        self._r_list = set()
        self._w_list = set()
        self._x_list = set()

    def poll(self, timeout):
        r, w, x = select.select(self._r_list, self._w_list, self._x_list,
                                timeout)
        results = defaultdict(lambda: 0x00)
        for p in [(r, IOLoop.READ), (w, IOLoop.WRITE), (x, IOLoop.ERROR)]:
            for fd in p[0]:
                results[fd] |= p[1]
        return results.items()

    def register(self, fd, mode):
        if mode & IOLoop.READ:
            self._r_list.add(fd)
        if mode & IOLoop.WRITE:
            self._w_list.add(fd)
        if mode & IOLoop.ERROR:
            self._x_list.add(fd)

    def unregister(self, fd):
        if fd in self._r_list:
            self._r_list.remove(fd)
        if fd in self._w_list:
            self._w_list.remove(fd)
        if fd in self._x_list:
            self._x_list.remove(fd)

    def modify(self, fd, mode):
        self.unregister(fd)
        self.register(fd, mode)

    def close(self):
        pass


class IOLoop(object):

    _EPOLLIN = 0x001
    _EPOLLPRI = 0x002
    _EPOLLOUT = 0x004
    _EPOLLERR = 0x008
    _EPOLLHUP = 0x010
    _EPOLLRDHUP = 0x2000
    _EPOLLONESHOT = (1 << 30)
    _EPOLLET = (1 << 31)

    NONE = 0
    READ = _EPOLLIN
    WRITE = _EPOLLOUT
    ERROR = _EPOLLERR | _EPOLLHUP

    _instance_lock = threading.Lock()

    def __init__(self):
        if hasattr(select, 'epoll'):
            self._impl = select.epoll()
            model = 'epoll'
        elif hasattr(select, 'kqueue'):
            self._impl = KqueueLoop()
            model = 'kqueue'
        elif hasattr(select, 'select'):
            self._impl = SelectLoop()
            model = 'select'
        else:
            raise Exception('can not find any available functions in select '
                            'package')
        self._fdmap = {}  # (f, handler)
        self._last_time = time.time()
        self._periodic_callbacks = []
        self._stopping = False
        self._timeout = Timeout()
        print('using event model: %s' % model)

    @staticmethod
    def instance():
        if not hasattr(IOLoop, "_instance"):
            with IOLoop._instance_lock:
                if not hasattr(IOLoop, "_instance"):
                    IOLoop._instance = IOLoop()
        return IOLoop._instance

    @staticmethod
    def current():
        current = getattr(IOLoop._current, "instance", None)
        if current is None:
            return IOLoop.instance()
        return current

    def poll(self, timeout=None):
        events = self._impl.poll(timeout)
        return [(self._fdmap[fd][0], fd, event) for fd, event in events]

    def register(self, f, mode, handler):
        fd = f.fileno()
        self._fdmap[fd] = (f, handler)
        self._impl.register(fd, mode)

    def add(self, f, mode, handler):
        return self.register(f, mode, handler)

    def remove(self, f):
        fd = f.fileno()
        del self._fdmap[fd]
        self._impl.unregister(fd)

    def add_periodic(self, callback):
        self._periodic_callbacks.append(callback)

    def remove_periodic(self, callback):
        self._periodic_callbacks.remove(callback)

    def modify(self, f, mode):
        fd = f.fileno()
        self._impl.modify(fd, mode)

    def stop(self):
        self._stopping = True

    def run(self):
        events = []
        while not self._stopping:
            asap = False
            try:
                events = self.poll(TIMEOUT_PRECISION)
            except (OSError, IOError) as e:
                if utils.errno_from_exception(e) in (errno.EPIPE, errno.EINTR):
                    # EPIPE: Happens when the client closes the connection
                    # EINTR: Happens when received a signal
                    # handles them as soon as possible
                    asap = True
                    print('poll:%s', e)
                else:
                    print('poll:%s', e)
                    import traceback
                    traceback.print_exc()
                    continue

            for sock, fd, event in events:
                handler = self._fdmap.get(fd, None)
                if handler is not None:
                    handler = handler[1]
                    try:
                        if not getattr(handler, "_keepalive", False):
                            self._timeout.update_activity(fd, handler)
                        handler.handle_events(sock, fd, event)
                    except (OSError, IOError) as e:
                        print(e)
            now = time.time()
            if asap or now - self._last_time >= TIMEOUT_PRECISION:
                self._timeout.cleanup()
                self._last_time = now

    def __del__(self):
        self._impl.close()


class Timeout(object):

    QUEUE_MAXLEN = 1024

    FD_POS_IN_QUEUE = dict()

    FD_QUEUE = list()

    TIMEOUT_OFFSET = 0

    FD_LASTACTIVITY = dict()

    FD_HANDLERS = dict()

    TIMEOUTS_CLEAN_SIZE = 512

    def update_activity(self, fd, handler):
        self.FD_LASTACTIVITY[fd] = time.time()
        pos = self.FD_POS_IN_QUEUE.get(fd, -1)
        if pos >= 0:
            self.FD_QUEUE[pos] = None
        l = len(self.FD_QUEUE)
        self.FD_QUEUE.append(fd)
        self.FD_POS_IN_QUEUE[fd] = l
        self.FD_HANDLERS[fd] = handler

    def cleanup(self):
        """"""
        if not self.FD_QUEUE:
            return
        now = time.time()
        size = len(self.FD_QUEUE)
        pos = self.TIMEOUT_OFFSET
        while pos < size:
            fd = self.FD_QUEUE[pos]
            if fd:
                if now - self.FD_LASTACTIVITY[fd] < 300:
                    break
                handler = self.FD_HANDLERS[fd]
                logging.info("connect %s:%s timeout" % handler._addr)
                handler.destroy()
                self.FD_QUEUE[pos] = None       # free memory
                self.FD_HANDLERS.pop(fd)     # reduce ref
                del self.FD_LASTACTIVITY[fd]
                del self.FD_POS_IN_QUEUE[fd]
                pos += 1
            else:
                pos += 1

        if pos > self.TIMEOUTS_CLEAN_SIZE and pos > size >> 1:
            self.FD_QUEUE = self.FD_QUEUE[pos:]
            for key in self.FD_POS_IN_QUEUE:
                self.FD_POS_IN_QUEUE[key] -= pos
                
            pos = 0
        self.TIMEOUT_OFFSET = pos

