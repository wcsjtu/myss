# Myss
![Build Status](https://travis-ci.org/wcsjtu/myss.svg?branch=master)

[中文文档](https://github.com/wcsjtu/myss/blob/master/README_CN.md)

A derivative project from ss. Except `encrypt` module, all clowwindy's code are redesigned for complexity and effiency. Compared with origin shaodowsocks, the main improvement is:

- native proxy conversion from http(s) to socks, now it could work without `privoxy`.

- auto config system proxy settings(Windows and Darwin. Linux doesn't support yet)

- simplified event handling process in `tcprelay`

- simpler and more efficient policy of `asyncdns`

- seperate local and remote code in `tcprelay`

- redesigned `lru_cache`. now there's no need to sweep cache periodically

- add `DNS Asynchronous Parse` function to udp forwarding

- tcp payload were buffered, so we can do anything on it, such as deep packet inspection, protocol conversion and etc.

## install

you can install this package using pip(depend on git cmd tool)

```shell
pip install git+https://github.com/wcsjtu/myss.git
```

or download source code, then

```shell
cd .
python setup.py install
```

## usage

Suppose `myss` have been installed according to tutorial above, you can see the usage of how to start myss server:

```shell
myss server --help      # see detail help info about start myss server
```

or start myss local by:

```shell
myss local -c path_to_config_file
```

If you won't install it, you can download the source code, and start myss service by:

```shell
cd myss
python manage.py server --help
```

Starting service via config file is recommended. The most commonly used parameters for `local` service are:

```python
{
    "rhost": "ip:port",             #remote service's ip and port, such as "192.168.1.2:8838"
    "local_address": "127.0.0.1",   #local service binding interface.
    "local_port": 1080,             #local socks5 proxy service binding port.
    "local_http_port": 1081,        #local http(s) proxy service binding port.
    "password": "pswd",             #pre-shared key between local and remote service
    "timeout": 300,                 #inteval to close non-activity connection
    "method": "aes-256-cfb",        #pre-shared encrypt method between local and remote service
    "proxy_mode": "pac",            #system proxy mode. one of `pac`, `global`, `off`
    "pac": "your path",             #path to your pac file. default is `./ss/config/pac`,
    "quiet": true                   #log level. if true, only print warning message
}
```

and for `remote` service are:

```json
{
    "server": "0.0.0.0",
    "server_port": 8838,
    "password": "pswd",
    "timeout": 300,
    "method": "aes-256-cfb",
    "fast_open": false,
    "log_file": "ssserver.log",
    "quiet": true
}
```

## TODO

- Python3.x support
- flow control
- ipv6 support
- more
