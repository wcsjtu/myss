# Myss

[English Doc](https://github.com/wcsjtu/myss/README.md)

山寨版的 ss. 复用了它的部分代码, 重构了代码的主结构, 优化了部分设计, 同时增加了一些功能, 主要是以下几点

- 原生的http(s)代理, 内置http(s) --> sock5的转换功能, 可以脱离privoxy工作.

- Windows和Mac上, 自动配置系统代理, 而且不用依赖.net框架

- 简化了 `tcprelay`的事件处理流程

- 更高效的异步DNS客户端

- 重构了`tcprelay`的代码, 分离了local和server的处理逻辑

- 重新设计`lru_cache`, 现在不用定时去清理缓存了

- 缓存了tcp负载, 使得程序具备了深度包检测和协议转换的能力. 原生的http(s)代理就是基于此设计实现的

## 安装

可以直接通过python的pip安装(依赖git的命令行工具), 

```shell
pip install git+https://github.com/wcsjtu/myss.git
```

如果没有git命令行工具, 可以通过源码安装

```shell
cd .
python setup.py install
```

如果实在安装不上, 或者不想安装, 也不影响使用, 程序提供了通过源码启动的方式, 具体参见下面的使用方式

## 使用

如果已经安装成功, 可以使用下面的命令来查看`remote service`的详细帮助信息

```shell
myss server --help      # see detail help info about start myss server
```

或者通过配置文件的方式, 来启动服务, 下面就是启动本地服务的命令:

```shell
myss local -c path_to_config_file
```

如果由于各种原因, 没有安装上, 可以通过下面的方式来启动:

```shell
python manage.py server --help
```

这里推荐使用配置文件的方式来启动服务, 因为后期会加上对配置文件的热更功能——修改配置文件后不用重启, 下面介绍一下常用的参数. 大部分参数与ss的意义相同.

下面是一个本地服务的配置文件

```js
{
    "rhost": "ip:port",             //远程服务的ip和端口, 比如 "192.168.1.2:8838"
    "local_address": "127.0.0.1",   //本地服务绑定的网卡, 一般是"127.0.0.1".
    "local_port": 1080,             //本地的socks5代理使用的端口, 默认是1080.
    "local_http_port": 1081,        //本地的http(s)代理使用的端口, 默认是1081.
    "password": "pswd",             //与远程服务预共享的密码, 本地与远程务必保持一致
    "timeout": 300,                 //不活跃连接的最大生存时间, 默认是300秒
    "method": "aes-256-cfb",        //与远程服务预共享的加密方式, 本地与远程务必保持一致
    "proxy_mode": "pac",            //系统代理模式. 有 `pac`, `global`, `off` 三种
    "pac": "your path",             //pac文件的路径, 默认在 `./ss/config/pac`.
    "quiet": true                   //日志级别, 安静模式下, 只会显示警告
}
```

下面是一个远程服务的配置文件:

```js
{
    "server": "0.0.0.0",        //远程服务绑定的网卡, 默认是"0.0.0.0", 除非你明确这个参数的意义, 否则别改
    "server_port": 8388,        //远程服务使用的端口, 默认8388. 千万别使用默认端口, 不然容易被封IP
    "password": "pswd",         //与本地服务预共享的密码
    "timeout": 300,             //不活跃连接的最大生存时间, 默认是300秒
    "method": "aes-256-cfb",    //与本地服务预共享的加密方式, 本地与远程务必保持一致
    "fast_open": false,
    "log_file": "ssserver.log",
    "quiet": true
}
```

## 建议

- 这里提供了默认的pac文件, 里面的域名可能不是最新的, 可以从网上下载最新的pac文件, 在启动本地服务时, 指定pac文件的位置即可. 修改pac文件后, 不用重启, 但是实际生效可能会有几秒的延时.

- 在mac上使用开启本地服务时, 建议使用sudo权限打开, 不然要输入好几次密码——因为要配置系统代理, 包括http(s), socks5, pac等等

## TODO

- 守护进程、多进程功能
- 服务端流量控制
- 完整的IPV6支持
- 更多的协议转换功能
