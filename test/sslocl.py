# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "..")
from ss.management import run

def main():
    sys.argv += ["local", "-c", "test/sslocal.json"]
    run()

if __name__ == "__main__":

    main()
