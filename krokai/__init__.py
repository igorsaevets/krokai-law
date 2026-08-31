# -*- coding: utf-8 -*-
"""krokai - a citation safety harness for AI-assisted legal work.

The one sentence that explains the whole package:

    **A grounded citation does not prove the quotation is real.**

Measured, on video, in a real matter: a model was asked to open a specific regulation and quote it.
It fetched the correct page, attached a correct and verifiable link to the correct URL, and then
**invented the text of the rule**. Every automated "did it check its sources" audit reported that
answer as 1/1 grounded and perfectly clean.

Only comparing the words against the actual document catches that. This package does that
comparison, and everything else here exists to make the comparison happen without anybody having to
remember to run it.
"""

__version__ = "0.10.1"
__all__ = ["__version__"]
