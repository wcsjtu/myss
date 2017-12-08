#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014-2015 clowwindy
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

from __future__ import absolute_import, division, print_function, \
    with_statement
import sys
import os
import socket
import struct
import re
import logging
import json
from ss import utils
from ss.lru_cache import LRUCache
from ss.ioloop import IOLoop


VALID_HOSTNAME = re.compile(br"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)

utils.patch_socket()


def is_valid_hostname(hostname):
    if len(hostname) > 255:
        return False
    if hostname[-1] == b'.':
        hostname = hostname[:-1]
    return all(VALID_HOSTNAME.match(x) for x in hostname.split(b'.'))


class InvalidDomainName(Exception):pass


class RR(object):
    """resource record"""

    __slots__ = ["domain_name", "qtype", "qcls", "ttl", "value"]

    def __init__(self, dn, qt, qc, ttl, val):
        self.domain_name = dn
        self.qtype = qt
        self.qcls = qc
        self.ttl = ttl
        self.value = val


class Response(object):
    DOMAIN_END = b"\x00"

    def __init__(self, d):
        self._offset = 0
        self._data = d

    def cut(self, i):
        up = self._offset + i
        t = self._data[self._offset:up]
        self._offset = up
        return t

    def __getitem__(self, i):
        return self._data[i]

    def cut_domain(self):
        """get domain from repsonse, return doamin 
        string and its length in protocol"""
        d = self._data
        domain_part = []
        up = 0
        i = self._offset
        while d[i] != self.DOMAIN_END:
            length = struct.unpack("!B", d[i])[0]
            if length >= 0xc0:
                if i >= self._offset:
                    self._offset += 2
                i = struct.unpack("!H", d[i:i+2])[0] -0xc000
                continue
            up = i + length + 1
            domain_part.append(d[i+1:up])
            if up >= self._offset:
                self._offset += (length + 1)
            i = up
        if up >= self._offset:
            self._offset += 1
        return ".".join(domain_part)

    
class DNSParser(object):

    QTYPE = (QTYPE_A, QTYPE_NS, QTYPE_CNAME, QTYPE_AAAA, QTYPE_ANY) = \
        (1, 2, 5, 28, 255)

    MAX_PART_LENGTH = 63

    QCLASS_IN = 1


    def build_request(self, hostname, qtype):
        count = struct.pack("!HHHH", 1, 0, 0, 0)
        header = os.urandom(2) + b"\x01\x00" + count
        parts = hostname.split(".")
        qname = []
        for p in parts:
            if len(p) > self.MAX_PART_LENGTH:
                raise InvalidDomainName(p)
            qname += [struct.pack("!B", len(p)), p]
        qname = ''.join(qname) + b"\x00"
        t_c = struct.pack("!HH", qtype, self.QCLASS_IN)
        question = qname + t_c
        return header + question

    def parse_response(self, response):
        resp = Response(response)
        resp.cut(6)     # ID and question number
        answer_rrs, authority_rrs, addtional_rrs = \
            struct.unpack("!HHH", resp.cut(6))
        query_domain = resp.cut_domain()
        query_type = resp.cut(2)
        query_cls = resp.cut(2)

        arrs = self.parse_rrs(resp, answer_rrs)
        aurrs = self.parse_rrs(resp, authority_rrs)
        adrrs = self.parse_rrs(resp, addtional_rrs)
        rrs = arrs + aurrs + adrrs
        return query_domain, rrs

    def parse_rrs(self, resp, rrs):
        rs = []
        for i in xrange(rrs):
            domain = resp.cut_domain()
            qtype, qcls, ttl, data_length = struct.unpack("!HHIH" ,resp.cut(10))
            if qtype == self.QTYPE_A:       # ipv4
                data = socket.inet_ntoa(resp.cut(data_length))
            elif qtype == self.QTYPE_AAAA:  # ipv6
                data = socket.inet_ntop(socket.AF_INET6,resp.cut(data_length))
            elif qtype in [self.QTYPE_NS, self.QTYPE_CNAME]:   # cname
                data = resp.cut_domain()
            record = RR(domain, qtype, qcls, ttl, data)
            rs.append(record)
        return rs


class DNSResolver(object):

    def __init__(self, io_loop, **config):
        self.io_loop = io_loop
        self._config = config
        self._dns_parser = DNSParser()
        self._hosts = {}
        self._cbs = {}  # {hostname: {cb:None, cb1:None}}
        self._hostname_status = {}
        self._cache = LRUCache(maxsize=10000)
        self._sock = None
        self._registered = False
        self._servers = None
        self._keepalive = True
        self._parse_resolv()
        self._parse_hosts()
        self.last_cache()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                                   socket.SOL_UDP)
        self._sock.setblocking(False)
        # TODO monitor hosts change and reload hosts
        # TODO parse /etc/gai.conf and follow its rules

    def _parse_resolv(self):
        self._servers = []
        try:
            with open('/etc/resolv.conf', 'rb') as f:
                content = f.readlines()
                for line in content:
                    line = line.strip()
                    if line:
                        if line.startswith(b'nameserver'):
                            parts = line.split()
                            if len(parts) >= 2:
                                server = parts[1]
                                if utils.is_ip(server) == socket.AF_INET:
                                    if type(server) != str:
                                        server = server.decode('utf8')
                                    self._servers.append(server)
        except IOError:
            pass
        if not self._servers:
            self._servers = ['8.8.4.4', '8.8.8.8']

    def _parse_hosts(self):
        etc_path = '/etc/hosts'
        if 'WINDIR' in os.environ:
            etc_path = os.environ['WINDIR'] + '/system32/drivers/etc/hosts'
        try:
            with open(etc_path, 'rb') as f:
                for line in f.readlines():
                    line = line.strip()
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        if utils.is_ip(ip):
                            for i in range(1, len(parts)):
                                hostname = parts[i]
                                if hostname:
                                    self._hosts[hostname] = ip
        except IOError:
            self._hosts['localhost'] = '127.0.0.1'

    def register(self):
        if self._registered:
            raise Exception('already add to loop')
        # TODO when dns server is IPv6
        
        if not self.io_loop:
            self.io_loop = IOLoop.current()
        self.io_loop.add(self._sock, IOLoop.READ, self)
        self.io_loop.add_periodic(self.handle_periodic)
        self._registered = True

    def _call_callback(self, hostname, ip, error=None):


        callbacks = self._cbs[hostname].keys()
        for callback in callbacks:
            if ip or error:
                callback((hostname, ip), error)
            else:
                callback((hostname, None),
                         Exception('unknown hostname %s' % hostname))
        self.del_callbacks(hostname)   # remove completed callback
        if hostname in self._hostname_status:       
            del self._hostname_status[hostname]     # remove qtype of hostname. 

    def _handle_data(self, data):
        try:
            hostname, rrs = self._dns_parser.parse_response(data)
        except Exception as e:
            logging.warn("parse dns response error: %s" % str(e), exe_info=True)
            return
        ip = ""
        for rr in rrs:
            if rr.qtype in [DNSParser.QTYPE_A, DNSParser.QTYPE_AAAA) and \
                rr.qcls == DNSParser.QCLASS_IN:
                ip = rr.value
                break
        qtype = self._hostname_status.get(hostname, DNSParser.QTYPE_AAAA)
        if not ip and qtype == DNSParser.QTYPE_A:   # if ipv4 didn't get an ip, try ipv6 again
            self._send_req(hostname, QTYPE_AAAA)    
            self._hostname_status[hostname] = DNSParser.QTYPE_AAAA  # update qtype
        elif ip:
            self._cache[hostname] = ip
            self._call_callback(hostname, ip)
        elif qtype == DNSParser.QTYPE_AAAA:
            logging.info("unable to resolve %s using both ipv4 and ipv6" % hostname)
            self._call_callback(hostname, None)
        else:
            logging.warn("impossible!!")
        


    def handle_events(self, sock, fd, event):
        if sock != self._sock:
            return
        if event & IOLoop.ERROR:
            logging.error('dns socket err')
            self.io_loop.remove(self._sock)
            self._sock.close()
            # TODO when dns server is IPv6
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM,
                                       socket.SOL_UDP)
            self._sock.setblocking(False)
            self.io_loop.add(self._sock, IOLoop.READ | IOLoop.ERROR, self.handle_events)
        else:
            data, addr = sock.recvfrom(1024)
            if addr[0] not in self._servers:
                logging.warn('received a packet other than our dns')
                return
            self._handle_data(data)

    def handle_periodic(self):
        #self._cache.sweep()
        pass
        
    def add_callback(self, hostname, callback):
        cbs = self._cbs.get(hostname, {})
        cbs.update(callback=None)
        self._cbs.update(hostname=cbs)
        

    def del_callbacks(self, hostname, callback=None):
        """if callback not given, delete all callbacks under hostname,
        otherwise, just delete the callback of hostname"""
        try:
            if callback:
                cbs = self._cbs[hostname]
                del cbs[callback]
                if not cbs:
                    del self._cbs[hostname]
            else:
                del self._cbs[hostname]
        except KeyError:
            pass

    def _send_req(self, hostname, qtype):
        req = self._dns_parser.build_request(hostname, qtype)
        for server in self._servers:
            logging.debug('resolving %s with type %d using server %s',
                          hostname, qtype, server)
            self._sock.sendto(req, (server, 53))

    def resolve(self,hostname, callback):
        if type(hostname) != bytes:
            hostname = hostname.encode('utf8')
        if not hostname:
            callback(None, Exception('empty hostname'))
        elif utils.is_ip(hostname):
            callback((hostname, hostname), None)
        elif hostname in self._hosts:
            logging.debug('hit hosts: %s', hostname)
            ip = self._hosts[hostname]
            callback((hostname, ip), None)
        elif hostname in self._cache:
            logging.debug('hit cache: %s', hostname)
            ip = self._cache[hostname]
            callback((hostname, ip), None)
        else:
            if not is_valid_hostname(hostname):
                callback(None, Exception('invalid hostname: %s' % hostname))
                return
            if hostname in self._cbs:        # if hostname is under-resolving, just adds cb to         
                self.add_callback(hostname,  # callback list, doesn't send new request any more.
                    callback)   
                return
            try:
                self._send_req(hostname, DNSParser.QTYPE_A) # ipv4 first. if failed, send ipv6 req
                self._hostname_status[hostname] = DNSParser.QTYPE_A
                self.add_callback(hostname, callback)
            except InvalidDomainName as e:
                logging.warn("invalid hostname when build dns request: %s" % hostname)

    def destroy(self):
        if self._sock:
            if self._registered:
                self.io_loop.remove_periodic(self.handle_periodic)
                self.io_loop.remove(self._sock)
            self._sock.close()
            self._sock = None
        self._registered = False
        self.on_exit()

    def last_cache(self):
        dns_cache_file = self._config.get("dns_cache")
        if not dns_cache_file:  # local
            return
        path = os.path.expanduser(dns_cache_file)
        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            os.makedirs(folder)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write('{}')
            return
        try:
            with open(path, "r") as f:
                cache = json.load(f)
            for k in cache:
                self._cache[k] = cache[k]
        except Exception:
            logging.warn("fail to load dns cache")
            return

    def on_exit(self):
        path = self._config.get("dns_cache")
        if not path:    # local
            return
        path = os.path.expanduser(path)
        keys = self._cache._cache.keys()
        dns_dict = dict()
        for k in keys:
            dns_dict[k] = self._cache[k]
        f = open(path, "w")
        try:
            import fcntl
            fcntl.lockf(f.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass
        finally:
            json.dump(dns_dict, f)
            f.close()
