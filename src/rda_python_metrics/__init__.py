"""rda_python_metrics: RDA metrics, usage, and accounting utility package.

This package exposes two parallel APIs:

1. Legacy module-based API (back-compat). Import the capitalized
   submodules and call their module-level functions, e.g.::

       from rda_python_metrics import PgIPInfo, PgView

2. Class-based API (preferred for new code). Import the class from the
   lower-case module and either instantiate or subclass it, e.g.::

       from rda_python_metrics.pg_ipinfo import PgIPInfo
       from rda_python_metrics.pg_view import PgView

The legacy submodules are eagerly imported below so that
``from rda_python_metrics import PgIPInfo`` continues to return the
module object that existing callers expect.
"""

from . import PgIPInfo, PgView

__version__ = "2.0.6"

__all__ = [
   "PgIPInfo",
   "PgView",
   "__version__",
]
