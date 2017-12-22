# -*- coding: utf-8 -*-
import logging
import socket
import errno
import os
import collections
from ss import encrypt
from ss import utils
from ss.ioloop import IOLoop
from ss.settings import settings
from .base import BaseTCPHandler, \
    RemoteMixin, LocalMixin, HttpLocalMixin

    
class ConnHandler(BaseTCPHandler):

    def __init__(self, io_loop, conn, addr, tags):
        self._encryptor = encrypt.Encryptor(settings['password'],
                                            settings['method'])
        BaseTCPHandler.__init__(self, io_loop, conn, addr, tags)

    def handle_events(self, sock, fd, events):
        """
        默认监听read和error, 回调结束后, 会判断当前_read_buf是否为空, 
        不为空则为peer增加write事件
        """
        if self._status == self.STAGE_CLOSED:
            logging.warning("socket %d already closed" % self._sock.fileno())
            return
        if events & IOLoop.ERROR:
            self.on_sock_error()

        default_events = IOLoop.ERROR | IOLoop.READ

        if events & IOLoop.READ:
            if self._status == self.STAGE_INIT:
                self.on_recv_nego()
            elif self._status == self.STAGET_SOCKS5_NEGO:
                self.on_recv_syn()
            elif self._status == self.STAGE_PEER_CONNECTED:
                self.on_read()
            else:
                # it will take few time transfer status from 
                # STAGE_SOCKS5_SYN to STAGE_DNS_RESOVED. During 
                # this period, fd may become readable. 
                self.on_read()
        if events & IOLoop.WRITE:
                self.on_write()

        if self._status == self.STAGE_CLOSED:       # socket may be closed in callback func
            return

        _events = default_events | IOLoop.WRITE if self.writable \
            else default_events
        self.update_events(_events)

        peer = self.peer
        if peer:
            peer_events = default_events | IOLoop.WRITE if peer.writable \
                else default_events
            peer.update_events(peer_events)

    @property
    def writable(self):
        return bool(self._write_buf or 
            (self.peer and self.peer._read_buf))


    def update_events(self, events):
        """"""
        if self._sock:
            self.io_loop.modify(self._sock, events)
            self._events = events
                
    def on_write(self):
        # NOTICE 写数据时, 都是从对方的read_buf取出数据写的
        num_bytes = 0
        peer_handler = self.peer     
               
        if not peer_handler:    # if peer not created
            write_buf = self._write_buf
        else:
            write_buf = peer_handler._read_buf
            if self._write_buf:     
                # self._write_buf中一般不会有数据, 有数据时
                # peer_handler._read_buf肯定为空, 此次操作
                # 时间为O(1)
                utils.merge_prefix(self._write_buf, self.BUF_SIZE)                    
                data = self._write_buf.popleft()
                write_buf.appendleft(data)   
                peer_handler._rbuf_size += len(data)
                self._wbuf_size -= len(data)


        if not write_buf:
            return num_bytes
        utils.merge_prefix(write_buf, self.BUF_SIZE)
        while write_buf:
            try:
                if not self._sock:
                    break
                length = self._sock.send(write_buf[0])
                if length:
                    utils.merge_prefix(write_buf, length)
                    write_buf.popleft()
                    num_bytes += length
                else:
                    break
            except (socket.error, IOError, OSError) as e:
                error_no = utils.errno_from_exception(e)
                if error_no in (errno.EAGAIN, errno.EINPROGRESS,
                                errno.EWOULDBLOCK):     # 缓冲区满
                    break
                else:
                    logging.error(e)
                    self.destroy()
                    break
        if not peer_handler:
            self._wbuf_size -= num_bytes
        else:
            peer_handler._rbuf_size -= num_bytes
        logging.info("send {:6d} B to   {:15s}:{:5d} ".format(num_bytes, *self._addr))
        return num_bytes

    def on_read(self):
        data = None
        if not self._sock:
            return
        try:
            data = self._sock.recv(self.BUF_SIZE)
        except (OSError, IOError) as e:
            if utils.errno_from_exception(e) in \
                    (errno.ETIMEDOUT, errno.EAGAIN, errno.EWOULDBLOCK):
                return
        if not data:
            self.destroy()
            return
        data = self._codec(data)
        self._read_buf.append(data)
        date_length = len(data)
        self._rbuf_size += date_length
        logging.info("recv {:6d} B from {:15s}:{:5d} ".format(date_length, *self._addr))
        if self._rbuf_size >= self.MAX_BUF_SIZE:
            logging.warn("connection: %s:%d read buffer over flow!" % self._addr)
            self.destroy()
        
    @property
    def togfw(self):
        #    0      0         1      1 
        # remote negative | local positive
        return self._tags == self.ISLOCAL

    def _codec(self, data):
        if getattr(self, "_direct_conn", False):
            func = lambda x: x
        else:
            func = self._encryptor.encrypt if self.togfw \
                else self._encryptor.decrypt
        return func(data)

    def destroy(self):
        if self._status == self.STAGE_CLOSED:
            logging.info('already destroyed')
            return
        self._status = self.STAGE_CLOSED
        if self._sock:
            logging.info("   socket connected to %s:%d closed!" % self._addr)
            self.io_loop.remove(self._sock)
            self._sock.close()
            self._sock = None
            if self._read_buf and self.peer and self.peer._sock:
                self.peer.on_write()    # 如果还有数据, 立即触发on_write
        if self.peer:
            op_sock = self.peer._sock
            if op_sock:
                logging.info("(R)socket connected to %s:%d closed!" % self.peer._addr)
                self.io_loop.remove(op_sock)
                op_sock.close()
                if self.peer:
                    self.peer._sock = None
        self._op_hdl_ref = None

    @property
    def peer(self):
        return self._op_hdl_ref() if self._op_hdl_ref else None

        
class ListenHandler(BaseTCPHandler):

    def __init__(self, io_loop, sa, conn_hdcls, dns_resolver=None):
        """
        @params:
            io_loop, event loop
            sa, ip and port
            conn_hdcls, handler class which handle each accepted connection, 
                        maybe the mixin of `ConnHandler` and `RemoteMixin`
            dns_resolver, need for ssserver
        """
        super(ListenHandler, self).__init__(io_loop, None, sa, self.HDL_LISTEN)
        self._sock = self.bind(sa)
        self._conn_hd_cls = conn_hdcls
        self._dns_resolver = dns_resolver
        self._keepalive = True

    def bind(self, sa):
        addrs = socket.getaddrinfo(sa[0], sa[1], 0, socket.SOCK_STREAM, socket.SOL_TCP)
        if not addrs:
            raise RuntimeError("can't get addrinfo for %s:%d" % tuple(sa))
        af, socktype, proto, canonname, sa_ = addrs[0]
        server_socket = socket.socket(af, socktype, proto)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(sa_)
        server_socket.setblocking(False)
        if settings.get("fast_open", False):
            try:
                server_socket.setsockopt(socket.SOL_TCP, 23, 5)
            except socket.error:
                logging.warning("fast open is not available!!")
        server_socket.listen(self.BACKLOG)
        return server_socket


    def handle_events(self, sock, fd, events):
        if self._status == self.STAGE_CLOSED:
            logging.warning("handler destoryed!")
            return
        if events & self.io_loop.ERROR:
            self.destroy()
            raise Exception('server_socket error')
        try:
            logging.info("accept")
            conn, addr = self._sock.accept()
            handler = self._conn_hd_cls(self.io_loop, conn, addr, self._dns_resolver, 
                                        self.HDL_NEGATIVE)
            handler.register()
        except (OSError, IOError) as e:
            err_no = utils.errno_from_exception(e)
            if err_no in (errno.EAGAIN, errno.EINPROGRESS,
                            errno.EWOULDBLOCK):
                return
            else:
                logging.error("fatal error: %s" % e)

    def destroy(self):
        self._status = self.STAGE_CLOSED
        self.io_loop.remove(self._sock)
        self._sock.close()


class RemoteConnHandler(ConnHandler, RemoteMixin):

    def __init__(self,  io_loop, conn, addr, dns_resolver, tags):
        ConnHandler.__init__(self, io_loop, conn, addr, tags)
        RemoteMixin.__init__(self, dns_resolver)


class LocalConnHandler(ConnHandler, LocalMixin):
    def __init__(self,  io_loop, conn, addr, dns_resolver, tags):
        ConnHandler.__init__(self, io_loop, conn, addr, tags)
        LocalMixin.__init__(self, dns_resolver)


class HttpLocalConnHandler(ConnHandler, HttpLocalMixin):

    def __init__(self,  io_loop, conn, addr, dns_resolver, tags):
        ConnHandler.__init__(self, io_loop, conn, addr, tags)
        HttpLocalMixin.__init__(self, dns_resolver)