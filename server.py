#!/usr/bin/env python3
"""
Root entry point wrapper for starting the Texas Surplus web application server.
"""
import os
import sys

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from server import main

if __name__ == '__main__':
    main()
