#
##################################################################################
#
#     Title: pgsyspath
#    Author: Zaihua Ji, zji@ucar.edu
#      Date: 10/21/2020
#   Purpose: python script to set sys.path properly to include paths for local
#            modules
#
# Work File: $DSSHOME/bin/python/pgsyspath.py*
#    Github: https://github.com/NCAR/rda-utility-programs.git
#
##################################################################################

import sys
import os
import re

#
# intinialize the sys.path to include paths for local modules
#
def include_local_paths():

   rpath = '/glade/u/home/rdadata'
   if re.match('PG', rpath): rpath = os.getenv('DSSHOME', '/glade/u/home/rdadata')

   # add more path to pgpaths list as needed
   pgpaths = [rpath + '/lib/python',
              rpath + '/lib/python/site-packages']
   for pgpath in pgpaths:
      if pgpath not in sys.path: sys.path.insert(0, pgpath)

#
# call to include local paths when this module is imported or run independently
#
include_local_paths()
