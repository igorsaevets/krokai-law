# -*- coding: utf-8 -*-
"""`python -m krokai ...` - the path that works with no installation at all.

Copying the folder and running this is a supported install method on purpose: the audience includes
people who are not allowed to run `pip install` on a work machine, and a tool a paralegal cannot
install is a tool that does not exist.
"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
