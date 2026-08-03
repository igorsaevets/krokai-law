# -*- coding: utf-8 -*-
"""`python -m krokai ...` AND `python <clone>/krokai ...` - the paths that need no installation.

Copying the folder and running this is a supported install method on purpose: the audience includes
people who are not allowed to run `pip install` on a work machine, and a tool a paralegal cannot
install is a tool that does not exist.

🔴 THE SECOND FORM WAS DOCUMENTED AND HAD NEVER WORKED. `INSTALL-FOR-AI.md` told the assistant to
run `python ~/tools/krokai/krokai init .` from the matter folder - and running a package DIRECTORY
executes this file as a top-level script with no parent package, so the relative import below blew
up with `attempted relative import with no known parent package`. Found on 2026-08-03 by executing
the install document end to end in a scratch folder, which no one had done: every earlier test ran
`-m` from inside the clone, where the working directory quietly supplies what the documented
command does not. A document is tested by executing it, on a machine where nothing is already set
up - reading it proves nothing.
"""
import os
import sys

if __package__ in (None, ""):
    # Directory-run: put the CLONE root (the package's parent) on sys.path and import absolutely.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from krokai.cli import main
else:
    from .cli import main

if __name__ == "__main__":
    sys.exit(main())
