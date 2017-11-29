# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import ss

setup(
    name="myss",
    version= "1.0.0",
    url = "https://github.com/wcsjtu/myss",
    description = "myss from shadowsocks",
    author = "wcsjtu",
    maintainer = "wcsjtu",
    maintainer_email = "wcsjtu@gmail.com",
    license = "BSD",
    packages = find_packages(),
    data_files = [("ss/config", ["ss/config/pac"])],
    package_data = {"ss": ["config/pac"]},
    test_suite="test.test_all",
    entry_points={
        'console_scripts':[
            "myss = ss.management:run",
        ]
    }
    )
