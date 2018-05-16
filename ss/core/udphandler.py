#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2015 clowwindy
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

# SOCKS5 UDP Request
# +----+------+------+----------+----------+----------+
# |RSV | FRAG | ATYP | DST.ADDR | DST.PORT |   DATA   |
# +----+------+------+----------+----------+----------+
# | 2  |  1   |  1   | Variable |    2     | Variable |
# +----+------+------+----------+----------+----------+

# SOCKS5 UDP Response
# +----+------+------+----------+----------+----------+
# |RSV | FRAG | ATYP | DST.ADDR | DST.PORT |   DATA   |
# +----+------+------+----------+----------+----------+
# | 2  |  1   |  1   | Variable |    2     | Variable |
# +----+------+------+----------+----------+----------+

# shadowsocks UDP Request (before encrypted)
# +------+----------+----------+----------+
# | ATYP | DST.ADDR | DST.PORT |   DATA   |
# +------+----------+----------+----------+
# |  1   | Variable |    2     | Variable |
# +------+----------+----------+----------+

# shadowsocks UDP Response (before encrypted)
# +------+----------+----------+----------+
# | ATYP | DST.ADDR | DST.PORT |   DATA   |
# +------+----------+----------+----------+
# |  1   | Variable |    2     | Variable |
# +------+----------+----------+----------+

# shadowsocks UDP Request and Response (after encrypted)
# +-------+--------------+
# |   IV  |    PAYLOAD   |
# +-------+--------------+
# | Fixed |   Variable   |
# +-------+--------------+

# HOW TO NAME THINGS
# ------------------
# `dest`    means destination server, which is from DST fields in the SOCKS5
#           request
# `local`   means local server of shadowsocks
# `remote`  means remote server of shadowsocks
# `client`  means UDP clients that connects to other servers
# `server`  means the UDP server that handles user requests

from __future__ import absolute_import, division, print_function, \
    with_statement
import weakref
import socket
import logging
import struct
import errno
import random
from functools import partial
from ss import encrypt, lru_cache, utils
from ss.ioloop import IOLoop
from ss.core.socks5 import parse_header
from ss.settings import settings
BUF_SIZE = 65536

def client_key(source_addr, server_af):
    # notice this is server af, not dest af
    return '%s:%s:%d' % (source_addr[0], source_addr[1], server_af)

class ConnHandler(object):

    SVR_TAG, LOC_TAG = 0, 1

    def __init__(self, io_loop, addr, af, tags, peer_ref):
        self.io_loop = io_loop
        self._addr = addr
        self._tags = tags       # 0 mean server , 1 means local
        self._peer_ref = peer_ref
        self._sock = self.create_sock(addr, af)
        self._keepalive = False
        self._registered = False
        self._closed = False

    def create_sock(self, sa, af):
        sock = socket.socket(af, socket.SOCK_DGRAM)
        sock.setblocking(False)
        return sock

    def register(self):
        if self._registered:
            logging.warning(" already registered!" )
            return
        if self._closed:
            raise RuntimeError("register a closed fd to ioloop" )
        if not self.io_loop:
            self.io_loop = IOLoop.current()
        self.io_loop.register(self._sock, IOLoop.READ|IOLoop.ERROR, self)
        self._events = IOLoop.READ|IOLoop.ERROR
        self._registered = True

    def handle_events(self, sock, fd, events):
        if events & IOLoop.ERROR:
            logging.error('UDP socket error')
            return
        data, r_addr = sock.recvfrom(BUF_SIZE)
        if not data:
            logging.debug('UDP handle_client: data is empty')
            return
        logging.debug("UDP: recv {:6d} B from {:15s}:{:5d} ".format(len(data), *r_addr))
        if self._tags == self.SVR_TAG:
            addrlen = len(r_addr[0])
            if addrlen > 255:
                # drop
                return
            data = utils.pack_addr(r_addr[0]) + struct.pack('>H', r_addr[1]) + data
            response = encrypt.encrypt_all(settings["password"], settings["method"], 1,
                                           data)
            if not response:
                return
        else:
            #data = data[3:]
            data = encrypt.encrypt_all(settings["password"], settings["method"], 0,
                                       data)
            response = data
            if not data:
                return
        header_result = parse_header(data)
        if header_result is None:
            return
        if self._tags == self.LOC_TAG:
            response = b'\x00\x00\x00' + response
        if self.peer_sock:
            self.peer_sock.sendto(response, self._r_addr)
            logging.debug(
                "UDP: send {:6d} B to   {:15s}:{:5d} ".format(len(response), *self._r_addr)
                )
        else:
            pass    # drop 

    def destroy(self):
        if self._closed:
            logging.info('already destroyed')
            return
        self.io_loop.remove(self._sock)
        self._sock.close()
        self._sock = None
        self._peer_ref = None
        self._r_addr = None
        self._closed = True
        logging.info('destroy udp socket')
    
    @property
    def peer_sock(self):
        if self._peer_ref and self._peer_ref():
            return self._peer_ref()._sock
        else:
            return None

class ListenHandler(object):

    SVR_TAG, LOC_TAG = 0, 1

    def __init__(self, io_loop, addr, conn_hdcls, tags, dns_resolver=None):
        self._addr = addr
        self.io_loop = io_loop
        self._conn_hd_cls = conn_hdcls
        self._keepalive = True
        self._registered = False
        self._closed = False
        self._sock = self.bind(addr)
        self._peer_ref_cache = {}       # {(ip, addr, af): handler_object}
        self._tags = tags
        self.dns_resolver = dns_resolver

    def bind(self, sa):
        addrs = socket.getaddrinfo(sa[0], sa[1], 0,
                                   socket.SOCK_DGRAM, socket.SOL_UDP)
        if len(addrs) == 0:
            raise Exception("can't get addrinfo for %s:%d" % tuple(sa))
        af, socktype, proto, canonname, sa = addrs[0]
        sock = socket.socket(af, socktype, proto)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(tuple(sa))
        sock.setblocking(False)
        return sock

    def _get_a_server(self):
        server = settings['server']
        server_port = settings['server_port']
        if type(server_port) == list:
            server_port = random.choice(server_port)
        if type(server) == list:
            server = random.choice(server)
        logging.debug('chosen server: %s:%d', server, server_port)
        return server, server_port

    def peer_sock(self, addr, af, r_addr):
        key = client_key(addr, af)
        ref = self._peer_ref_cache.get(key, None)
        if ref and ref():
            ref()._r_addr = r_addr
            return ref()._sock
        else:
            peer_ref = weakref.ref(self)
            handler = self._conn_hd_cls(self.io_loop, addr, af, 
                self._tags, peer_ref)
            handler._r_addr = r_addr
            handler.register()
            self._peer_ref_cache[key] = weakref.ref(handler)
            return handler._sock
            
    def pre_dns_resolved(self, data, hostname, port, r_addr, result, error):
        if error:
            logging.error(error)
            return
        if not result:return
        ip = result[1]
        if not ip:return
        addrs = socket.getaddrinfo(ip, port, 0, 
            socket.SOCK_DGRAM, socket.SOL_UDP)  # for ip, will block??
        if not addrs:
            return
        af, socktype, proto, canonname, sa = addrs[0]
        peer_sock = self.peer_sock((ip, port), af, r_addr)
        try:
            if peer_sock:
                peer_sock.sendto(data, (ip, port))
        except IOError as e:
            err = utils.errno_from_exception(e)
            if err in (errno.EINPROGRESS, errno.EAGAIN):
                pass
            else:
                logging.error(e, exc_info=True)

    def handle_events(self, sock, fd, events):
        if events & IOLoop.ERROR:
            logging.error('UDP listen socket error')
            return
        data, r_addr = sock.recvfrom(BUF_SIZE)
        if not data:
            logging.debug('UDP handle_server: data is empty')
        if self._tags == self.LOC_TAG:
            frag = utils.ord(data[2])
            if frag != 0:
                logging.warn('drop a message since frag is not 0')
                return
            else:
                data = data[3:]
        else:
            data = encrypt.encrypt_all(settings["password"], 
                settings["method"], 0, data)   # decrypt
            if not data:
                logging.debug('UDP handle_server: data is empty after decrypt')
                return
        header_result = parse_header(data)
        if header_result is None:
            return
        addrtype, dest_addr, dest_port, header_length = header_result
        if self._tags == self.LOC_TAG:
            dest_addr, dest_port = self._get_a_server()
            data = encrypt.encrypt_all(settings["password"], 
                settings["method"], 1, data)
        else:
            data = data[header_length:]
        if not data:
            return
        on_dns_resolved = partial(self.pre_dns_resolved, data, 
            dest_addr, dest_port, r_addr)
        self.dns_resolver.resolve(dest_addr, on_dns_resolved)

    def register(self):
        if self._registered:
            logging.warn("udp listen socket has been already registered!")
            return
        if self._closed:
            raise Exception('already closed')
        if not self.io_loop:
            self.io_loop = IOLoop.current()
        self.io_loop.register(self._sock, IOLoop.READ|IOLoop.ERROR, self)
        self._events = IOLoop.READ|IOLoop.ERROR
        self._registered = True

    def destroy(self):
        if self._closed:
            logging.info('already destroyed')
            return
        self.io_loop.remove(self._sock)
        self._sock.close()
        self._sock = None
        self._peer_ref_cache = {}   # free memory
        self._closed = True
        logging.info('destroy udp listen socket')

