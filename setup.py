# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import ss

setup(
    name="myss",
    version= "0.0.1",
    url = "https://www.wchaos.cn/weblog",
    description = "myss from shadowsocks",
    author = "wcsjtu",
    maintainer = "wcsjtu",
    maintainer_email = "wcsjtu@gmail.com",
    license = "BSD",
    packages = find_packages(),
    entry_points={
        'console_scripts':[
            "myss = ss.management:run",
        ]
    }
    )
