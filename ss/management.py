# -*- coding: utf-8 -*-
import argparse
import logging
import sys
import os
import signal
import json
from ss import utils

def to_bytes(s):
    if type(s) != bytes:
        return s.encode("utf8")
    return s


class Command(object):

    DESC = "A fast tunnel proxy that helps you bypass firewalls."
    USAGE="myss <subcommand> [options] [args]"

    DEST_K = {
              "subcmd": "subcmd", 
              "action": "-d", 
              "pid_file": "--pid-file",
              "log_file": "--log-file", 
              "config": "-c", 
              "password": "-p",
              "method": "-m", 
              "timeout": "-t", 
              "fast_open": "--fast-open",
              "server": "-s", 
              "workers": "--workers", 
              "server_port": "-P",
              "forbidden_ip": "--forbidden-ip", 
              "manager_address": "--manager-address",
              "local_address": "-s", 
              "local_port": "-P", 
              "rhost": "-H", 
              "user": "--user",
              "gfwlist": "--gfw-list", 
              "quiet": "--quiet", 
              "verbose": "-v"
            }

    def __init__(self, parser=None):
        
        self.parser = parser if parser else \
                argparse.ArgumentParser(description=self.DESC,
                usage=self.USAGE
                    )
        subcommand = self.parser.add_subparsers(title="subcommands", 
                        prog="run myss as", dest="subcmd")
        self.local_parser = subcommand.add_parser("local")
        self.server_parser = subcommand.add_parser("server")
        self.add_server_argument()
        self.add_local_argument()

    def add_arg(self, parser, **options):
        k = self.DEST_K[options["dest"]]
        parser.add_argument(k, **options)

    def add_general_argument(self, parser):
        parser = parser.add_argument_group("General options")
        self.add_arg(parser, dest="verbose", help="verbose mode")

        self.add_arg(parser, help="command for daemon mode", dest="action",
                     choices=["start", "stop", "restart"])

        self.add_arg(parser, help="pid file for daemon mode", 
                     type=self._check_path, dest="pid_file")

        self.add_arg(parser, help="log file for daemon mode", 
                     type=self._check_path, dest="log_file")

        self.add_arg(parser, dest="user", help="username to run as")
        self.add_arg(parser, dest="quiet", help="quiet mode, only show warnings and errors",
                     action='store_true')

    def add_common_argument(self, parser):
        self.add_arg(parser, metavar="CONFIG", type=self._check_config,
                     help="path to config file, if this parameter is specified," 
                    "all other parameters will be ignored!", 
                    dest="config")
        
        self.add_arg(parser, metavar="PASSWORD", required=True,
                     help="password", dest="password")

        self.add_arg(parser, metavar="METHOD", default=to_bytes("aes-256-cfb"),
                     help="encryption method, default: aes-256-cfb", 
                     type=self._check_method, dest="method")

        self.add_arg(parser, metavar="TIMEOUT", default=300, 
                     type=self._check_timeout, dest="timeout",
                     help="timeout in seconds for idle connection, default: 300")

        self.add_arg(parser, action='store_true', dest="fast_open",
                     help="use TCP_FASTOPEN, requires Linux 3.7+")
        
    def add_server_argument(self):
        
        parser = self.server_parser
        self.add_arg(parser, dest="workers", type=self._check_workers, metavar="WORKERS",
                     help="number of workers, available on Unix/Linux,"
                     " count of cpu cores is recommended.",
                     default=self._default_workers())

        self.add_arg(parser, metavar="ADDR", dest="server", type=self._check_addr,
                     default=to_bytes("0.0.0.0"), required=True, 
                     help=" hostname or ipaddr, default is 0.0.0.0")

        self.add_arg(parser, metavar="PORT", type=int, 
                     default=8388, required=True,
                     help="port, default: 8388", dest="server_port")
        self.add_common_argument(parser)
        self.add_arg(parser, type=self._check_iplist, 
                     metavar="IPLIST", dest="forbidden_ip",
                     help="comma seperated IP list forbidden to connect")

        self.add_arg(parser, dest="manager_address",
                     help="optional server manager UDP address, see wiki")
        self.add_general_argument(self.server_parser)

    def add_local_argument(self):
        parser = self.local_parser
        self.add_arg(parser, metavar="ADDR", dest="local_address", 
                     default="127.0.0.1",
                     help="interface for local server to listen on, "
                     "default is 127.0.0.1" , type=self._check_addr)

        self.add_arg(parser, metavar="PORT", type=int, default=1080,
                     help="local listen port, default: 1080", 
                     dest="local_port" )

        self.add_arg(parser, metavar="REMOTE-HOST", dest="rhost",
                     help="remote ss server host, format is hostname:port"
                     "eg. ssbetter.org:8888", required=True, type=self._check_rhost)

        self.add_common_argument(parser)

        self.add_arg(parser, type=self._check_iplist, metavar="IPLIST",
                     help="a file which contains host forbidden by gfw",
                     dest="gfwlist", default=[])
        self.add_general_argument(self.local_parser)

    def _to_abspath(self, p):
        is_absolute = os.path.isabs(p)        
        if not is_absolute:
            basedir = os.getcwd()
            p = os.path.join(basedir, p)
        return p

    def _check_rhost(self, r):
        try:
            h, p = r.split(":")
            if h.startswith("127") or \
                h == "0.0.0.0":
                logging.warn("make sure your remote host config `%s` is right" % r)
            return h, int(p)
        except Exception:
            raise argparse.ArgumentTypeError("invalid rhost value `%s`" % r)

    def _check_addr(self, addr):
        return to_bytes(addr)

    def _default_workers(self):
        from multiprocessing import cpu_count
        if os.name != "posix":
            return 1
        else:
            return cpu_count()

    def _check_workers(self, c):
        try:
            c = int(c)
            if os.name != "posix" and c > 1:
                logging.warn("fork mode is only support on `posix`, "
                             "other platform worker count is limit 1")
                c = 1
            return c
        except ValueError:
            raise argparse.ArgumentTypeError("invalid int value: '%s'" % c)

    def _check_timeout(self, t):
        try:
            t = int(t)
        except ValueError:
            raise argparse.ArgumentTypeError("invalid int value: '%s'" % t)
        if t < 300:
            logging.warn("your timeout `%d` seems too short" % t)
        elif t > 600:
            logging.warn("your timeout `%d` seems too long" % t)
        return t

    def _check_pswd(self, pswd):
        return to_bytes(pswd)

    def _check_method(self, m):
        m = m.lower()
        if m in ["table", "rc4"]:
            logging.warn("%s is not safe; please use a safer cipher" 
                         " like `AES-256-CFB` is recommended." % m)
        return to_bytes(m)

    def _check_path(self, p):
        p = self._to_abspath(p)
        parent = os.path.dirname(p)
        if not os.access(parent, os.W_OK):
            raise argparse.ArgumentTypeError("can't write to %s, Permission Denied" % p)
        return p
        
    def _check_config(self, f):
        f = self._to_abspath(f)
        if not os.path.exists(f):
            raise argparse.ArgumentTypeError("config file `%s` doen't exist!" % f)
        try:
            with open(f, "r") as f:
                cfg = json.load(f)
            if "password" not in cfg:
                raise argparse.ArgumentTypeError("`password` must be specified in config file")
            cfg["password"] = to_bytes(cfg["password"])
            cfg["method"] = to_bytes(cfg["method"])
            return cfg
        except ValueError:
            raise argparse.ArgumentTypeError("config file must be json format")

    def _check_iplist(self, f):
        import re
        f = self._to_abspath(f)
        if not os.path.exists(f):
            raise argparse.ArgumentTypeError("iplist file `%s` doen't exist!" % f)
        try:
            with open(f, "r") as f:
                iplist = json.load(f)
            r = [re.compile(item) for item in iplist]   # any other has better way to match hostname?
            return r
        except ValueError:
            raise argparse.ArgumentTypeError("iplist file must be json format")

    def _cfg_param(self, args):
        cfg = None
        for i, arg in enumerate(args):
            if arg == "-c":
                if i + 1 >= len(args):
                    cfg = None
                else:
                    cfg = args[i+1]
                break
            elif arg.startswith("-c"):
                cfg = arg.strip("-c")
                break
        return cfg

    def gen_argv(self, subcmd, cfg):
        argv = [subcmd]
        for key in cfg:
            k = self.DEST_K.get(key)
            if k:
                if type(cfg[key]) is bool:
                    if cfg[key]:argv += [k, ]
                else:
                    argv += [k, str(cfg[key])]
        return argv

    def parse(self, args=None):
        if not args:
            args = sys.argv[1:]
        cfg = self._cfg_param(args)
        d = lambda p: p.__dict__
        if args and cfg:
            subc = args[0]
            config = self._check_config(cfg)
            args = self.gen_argv(subc, config)
        return d(self.parser.parse_args(args))
            

def get_cofing_from_cli():
    from ss import settings
    cmd = Command()
    cfg = cmd.parse()
    if "rhost" in cfg:
        cfg["server"], cfg["server_port"] =  cfg["rhost"]
        del cfg["rhost"]
    settings.settings.__dict__ = cfg
    config_logging(cfg)
    return cfg

def run(io_loop=None):
    config = get_cofing_from_cli()
    
    # if not io_loop:
    #     io_loop = IOLoop.current()
    subcmd = config.get("subcmd")
    handlers = {"local": run_local, "server": run_server}
    return handlers[subcmd](io_loop, config)

def run_local(io_loop, config):
    from ss.core import tcphandler, udphandler
    from ss.core.asyncdns import DNSResolver
    try:
        sa = config['local_address'], config['local_port']
        logging.info("starting local at %s:%d" % sa)
        dns_resolver = DNSResolver(io_loop)
        tcp_server = tcphandler.ListenHandler(io_loop, sa, 
            tcphandler.LocalConnHandler, dns_resolver, **config)
        udp_server = udphandler.ListenHandler(io_loop, sa, 
            udphandler.ConnHandler, 1, dns_resolver, **config)  # 1 means local
        dns_resolver.register()
        udp_server.register()
        tcp_server.register()

        def on_quit(s, _):
            logging.warn('received SIGQUIT, doing graceful shutting down..')
            tcp_server.destroy()
            udp_server.destroy()

        def on_interrupt(s, _):
            sys.exit(1)
            
        signal.signal(signal.SIGINT, on_interrupt)    
        signal.signal(getattr(signal, 'SIGQUIT', signal.SIGTERM), on_quit)
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

    dns_resolver = DNSResolver(io_loop)
    tcp_server = tcphandler.ListenHandler(io_loop, sa, 
        tcphandler.RemoteConnHandler, dns_resolver, **config)
    upd_server = udphandler.ListenHandler(io_loop, sa, 
        udphandler.ConnHandler, 0, dns_resolver, **config)
    servers = [dns_resolver, tcp_server, upd_server]

    def on_quit(s, _):
        logging.warn('received SIGQUIT, doing graceful shutting down..')
        for server in servers:
            server.destroy()
        logging.warn('all servers have been shut down')

    def start():
        
        try:
            for server in servers:
                server.register()
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
            signal.signal(signal.SIGTERM, on_master_exit)
            signal.signal(signal.SIGQUIT, on_master_exit)
            signal.signal(signal.SIGINT, on_master_exit)

            for server in servers:
                server._sock.close()
            #for child in children:
            #    os.waitpid(child, 0)
    else:
        logging.info('worker started')
        start()

def config_logging(cfg):
    logging.getLogger('').handlers = []
    kwargs = dict(
        format='%(asctime)s %(levelname)-8s lineno[%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    kwargs["level"] = logging.WARN if cfg.get("quiet") \
        else logging.INFO
    if kwargs.get("log_file"):
        kwargs["filename"] = kwargs["log_file"]

    logging.basicConfig(**kwargs)

if __name__ == "__main__":
    c = Command()
    print c.parse()