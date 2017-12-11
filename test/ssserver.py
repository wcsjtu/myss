# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, "..")
from ss.management import run

def main():
    try:
        folder = os.path.dirname(__file__)
        path = os.path.join(folder, "ssserver.json")
    except Exception as e:
        path = "test/ssserver.json"
    sys.argv += ["server", "-c", path]
    run()

if __name__ == "__main__":

    main()
