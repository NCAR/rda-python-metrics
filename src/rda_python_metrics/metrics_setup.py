#!/usr/bin/env python3
#
##################################################################################
#
#     Title: metrics-setup
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 2025-05-13
#   Purpose: Display post-install setup guide for rda_python_metrics setuid
#            programs (logarch).  Shown automatically when setuid_logarch is
#            invoked directly before the pywrapper setuid entry is configured.
#
#    Github: https://github.com/NCAR/rda-python-metrics.git
#
##################################################################################

import os
import sys


def main():
   """Display the rda_python_metrics setuid setup guide and exit.

   Reads metrics_setup.usg bundled with this package and pages it via
   'more'.  Called directly via the metrics-setup console script, or
   triggered automatically when setuid_logarch is invoked before the
   pywrapper symlink has been created.
   """
   usgfile = os.path.join(os.path.dirname(__file__), 'metrics_setup.usg')
   os.system("more " + usgfile)
   sys.exit(0)


if __name__ == "__main__": main()
