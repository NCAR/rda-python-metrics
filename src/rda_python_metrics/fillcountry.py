#!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillcountry
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2022-03-11
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to fill missing country field from email info for
#             given table name
#
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
###############################################################################
#
import sys
import re
from rda_python_common import PgLOG
from rda_python_common import PgIMMA
from rda_python_common import PgUtil
from rda_python_common import PgDBI

#
# main function to run this program
#
def main():

   argv = sys.argv[1:]
   tables = ['allusage', 'user', 'wuser']
   table = None
   
   # check command line
   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
      elif re.match(r'^-.*', arg):
         PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGEREX)
      elif not table:
         table = arg
      else:
         PgLOG.pglog(arg + ": one table name at a time", PgLOG.LGEREX)
   
   if not table:
      print("Usage: fillcountry TableName\n")
      sys.exit(0)
   elif table not in tables:
      PgLOG.pglog("{}: table name must be ({})".format(table, '|'.join(tables)), PgLOG.LGEREX)

   PgDBI.dssdb_dbname()
   PgLOG.cmdlog("fillcountry {}".format(' '.join(argv)))

   process_countries(table)
   
   sys.exit(0)

def process_countries(table):

   pgrecs = PgDBI.pgmget(table, "email", "country IS NULL", PgLOG.LOGWRN)

   cntall = len(pgrecs['email']) if pgrecs else 0
   PgLOG.pglog("Set {} record(s) for missing country in table {}".format(cntall, table), PgLOG.LOGWRN)
   if not cntall: return

   cntmod = 0
   for i in range(cntall):
      if i and (i % 500) == 0:
         PgLOG.pglog("{}/{} Records modified/processed".format(cntmod, i), PgLOG.WARNLG)

      email = pgrecs['email'][i]
      record = {'country' : PgDBI.email_to_country(email)}
      cntmod += PgDBI.pgupdt(table, record, "email = '{}' AND country IS NULL".format(email), PgLOG.LOGWRN)

   PgLOG.pglog("{} Record(s) modified in table '{}'".format(cntmod, table), PgLOG.LOGWRN)

#
# call main() to start program
#
if __name__ == "__main__": main()
