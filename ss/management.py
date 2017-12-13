# -*- coding: utf-8 -*-
import logging
import sys
import os
import signal
from ss import utils, cli, wrapper
from ss.config import Switcher

def set_proxy_mode(config):
    modename = config["proxy_mode"]
    if modename == "pac":
        from ss.watcher import Pac
        Switcher().shift(Switcher.MODE_PAC, **config)
        Pac.load(**config)
    elif modename == "global":
        Switcher().shift(Switcher.MODE_GLB, **config)
    elif modename == "off":
        Switcher().shift(Switcher.MODE_OFF, **config)

def run(io_loop=None):
    config = cli.config()
    
    # if not io_loop:
    #     io_loop = IOLoop.current()
    subcmd = config.get("subcmd")
    handlers = {"local": run_local, "server": run_server}
    return handlers[subcmd](io_loop, config)

def run_local(io_loop, config):
    from ss.core import tcphandler, udphandler
    from ss.core.asyncdns import DNSResolver
    from ss.ioloop import IOLoop
    from ss.watcher import Scheduler, Pac
    if not io_loop:
        io_loop = IOLoop.current()
    try:
        sa = config['local_address'], config['local_port']
        logging.info("starting local at %s:%d" % sa)
        dns_resolver = DNSResolver(io_loop, **config)
        tcp_server = tcphandler.ListenHandler(io_loop, sa, 
            tcphandler.LocalConnHandler, dns_resolver, **config)
        udp_server = udphandler.ListenHandler(io_loop, sa, 
            udphandler.ConnHandler, 1, dns_resolver, **config)  # 1 means local
        servers = [dns_resolver, tcp_server, udp_server]

        if config.get("local_http_port"):
            http_sa = config['local_address'], config['local_http_port']
            logging.info("starting local http tunnel at %s:%d" % http_sa)
            http_tunnel = tcphandler.ListenHandler(io_loop, http_sa, 
                tcphandler.HttpLocalConnHandler, dns_resolver, **config)
            servers.append(http_tunnel)

        for server in servers:
            server.register()
            wrapper.onexit(server.destroy)
            
        wrapper.register(['SIGQUIT', 'SIGINT', 'SIGTERM'], 
            wrapper.exec_exitfuncs)
        schd = Scheduler(**config)
        schd.register(Pac(15, 1, config))
        schd.start()
        set_proxy_mode(config)
        io_loop.run()
    except Exception as e:
        logging.error(e, exc_info=True)
        sys.exit(1)

def run_server(io_loop, config):
    from ss.core import tcphandler, udphandler
    from ss.core.asyncdns import DNSResolver
    from ss.ioloop import IOLoop
    sa = config['server'], config['server_port']
    logging.info("starting server at %s:%d" % sa)

    dns_resolver = DNSResolver(io_loop, **config)
    tcp_server = tcphandler.ListenHandler(io_loop, sa, 
        tcphandler.RemoteConnHandler, dns_resolver, **config)
    upd_server = udphandler.ListenHandler(io_loop, sa, 
        udphandler.ConnHandler, 0, dns_resolver, **config)
    servers = [tcp_server, upd_server, dns_resolver]


    def start():
        try:
            for server in servers:
                server.register()
                wrapper.onexit(server.destroy)
            wrapper.register(['SIGQUIT', 'SIGINT', 'SIGTERM'], 
                wrapper.exec_exitfuncs)
            io_loop = IOLoop.current()
            io_loop.run()
        except Exception as e:
            logging.error(e, exc_info=True)
            sys.exit(1)

    workers = config.get("workers", 1)
    if workers > 1:
        children = []
        def on_master_exit(s, _):
            for pid in children:
                try:
                    os.kill(pid, s)
                    os.waitpid(pid, 0)
                except OSError:  # child may already exited
                    pass
            sys.exit(0)

        is_child = False
        for i in range(workers):
            rpid = os.fork()
            if rpid == 0:
                logging.info('worker started')
                is_child = True
                start()
                break
            else:
                children.append(rpid)
        if not is_child:
            wrapper.register(['SIGQUIT', 'SIGINT', 'SIGTERM'], 
                on_master_exit)

            for server in servers:
                server._sock.close()
            #for child in children:
            #    os.waitpid(child, 0)
    else:
        logging.info('worker started')
        start()


