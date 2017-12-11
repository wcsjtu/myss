# Myss

A derivative project from [shadowsocks](https://github.com/shadowsocks/shadowsocks/tree/master). Except `encrypt` module, all clowwindy's code are redesigned for complexity and effiency. Compared with origin shaodowsocks, the main improvement is:

- native proxy conversion from http(s) to socks, now it could work without `privoxy`.

- simplified event handling process in `tcprelay`

- simpler and more efficient policy of `asyncdns`

- seperate local and remote code in `tcprelay`

- redesigned `lru_cache`. now there's no need to sweep cache periodically

- add `DNS Asynchronous Parse` function to udp forwarding

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

## TODO

- daemon mode
- flow control
- ipv6 support
- auto config when pac changed
- more