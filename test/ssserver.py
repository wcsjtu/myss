# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "..")
from ss.management import run

def main():
    
    sys.argv += ["server", "-c", "ssserver.json"]
    run()

if __name__ == "__main__":

    main()
