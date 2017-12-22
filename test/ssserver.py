# -*- coding: utf-8 -*-
import sys
import os
try:
    pwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:
    pwd = ".."
sys.path.insert(0, pwd)

from ss.management import run

def main():
    path = os.path.join(pwd, "test/ssserver.json")
    sys.argv += ["server", "-c", path]
    run()

if __name__ == "__main__":

    main()
