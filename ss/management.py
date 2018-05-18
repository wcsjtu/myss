# -*- coding: utf-8 -*-
import logging
import sys
import os
import signal
from functools import partial
from ss import utils, cli, wrapper
from ss.config import set_proxy_mode
from ss.settings import settings
from ss import watcher
from ss.core import tcphandler, udphandler
from ss.core.asyncdns import DNSResolver
from ss.ioloop import IOLoop

def run(io_loop=None):
    cli.parse_cli()
    
    # if not io_loop:
    #     io_loop = IOLoop.current()
    subcmd = settings.get("subcmd")
    handlers = {"local": run_local, "server": run_server}
    return handlers[subcmd](io_loop)

def run_local(io_loop):
    
    if not io_loop:
        io_loop = IOLoop.current()
    try:
        sa = settings['local_address'], settings['local_port']
        logging.info("starting local at %s:%d" % sa)
        dns_resolver = DNSResolver(io_loop)
        tcp_server = tcphandler.ListenHandler(io_loop, sa, 
            tcphandler.LocalConnHandler, dns_resolver)
        udp_server = udphandler.ListenHandler(io_loop, sa, 
            udphandler.ConnHandler, 1, dns_resolver)  # 1 means local
        servers = [dns_resolver, tcp_server, udp_server]

        if settings.get("local_http_port"):
            http_sa = settings['local_address'], settings['local_http_port']
            logging.info("starting local http tunnel at %s:%d" % http_sa)
            http_tunnel = tcphandler.ListenHandler(io_loop, http_sa, 
                tcphandler.HttpLocalConnHandler, dns_resolver)
            servers.append(http_tunnel)

        for server in servers:
            server.register()
            wrapper.onexit(server.destroy)
            
        wrapper.register(['SIGQUIT', 'SIGINT', 'SIGTERM'], 
            wrapper.exec_exitfuncs)
        wrapper.exec_startfuncs(None, None)
        io_loop.run()
    except Exception as e:
        logging.error(e, exc_info=True)
        sys.exit(1)

def on_master_exit(s, frame, children):
    """only for non-daemon mode"""
    for pid in children:
        try:
            os.kill(pid, s)
            print("kill subprocess %d" % pid)
            os.waitpid(pid, 0)
        except OSError:  # child may already exited
            pass
    sys.exit(0)

def run_server(io_loop):
    sa = settings['server'], settings['server_port']
    logging.info("starting server at %s:%d" % sa)

    dns_resolver = DNSResolver(io_loop)
    tcp_server = tcphandler.ListenHandler(io_loop, sa, 
        tcphandler.RemoteConnHandler, dns_resolver)
    udp_server = udphandler.ListenHandler(io_loop, sa, 
        udphandler.ConnHandler, 0, dns_resolver)
    servers = [tcp_server, udp_server, dns_resolver]


    def start():
        try:
            for server in servers:
                server.register()
                wrapper.onexit(server.destroy)
            io_loop = IOLoop.current()
            io_loop.run()
        except Exception as e:
            logging.error(e, exc_info=True)
            sys.exit(1)

    
    print(settings)
    workers = settings.get("workers", 1)
    is_daemon = settings["fork"]

    children = []
    if not is_daemon:
        for _ in range(workers-1):
            rpid = os.fork()
            if rpid:
                print("sub process %d forked" % rpid)
                children.append(rpid)
            else:
                logging.info("proxy start in sub process %d " % os.getpid())
                return start()
        if children:
            wrapper.register(
                ['SIGQUIT', 'SIGINT', 'SIGTERM'],
                partial(on_master_exit, children=children)
            )
        logging.info("proxy start in master process %d" % os.getpid())
        return start()
    else:
        for _ in range(workers):
            rpid = os.fork()
            if rpid:
                print("sub process %d forked" % rpid)
                children.append(rpid)
            else:
                logging.info("proxy start in sub process %d " % os.getpid())
                return start()
        if settings["pid_file"]:
            with open(settings["pid_file"], "w") as f:
                sc = [str(pid) for pid in children]
                f.write(" ".join(sc))
        print("all pids are written in pid file %s" % settings["pid_file"])
        print("%d workers spwaned, now master process exit" % workers)
        sys.exit(0)
    

