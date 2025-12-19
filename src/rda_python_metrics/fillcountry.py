#!/usr/bin/env python3/
###############################################################################
#     Title : fillcountry
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2022-03-11
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-17 convert to class FillCountry
#   Purpose : python program to fill missing country field from email info for
#             given table name
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import sys
import re
from rda_python_common.pg_dbi import PgDBI

class FillCountry(PgDBI):
   def __init__(self):
      super().__init__()
      self.tables = ['allusage', 'user', 'wuser']
      self.table = None

   # function to read paramters
   def read_parameter(self):
      argv = sys.argv[1:]
      # check command line
      for arg in argv:
         if arg == "-b":
            self.PGLOG['BCKGRND'] = 1
         elif re.match(r'^-.*', arg):
            self.pglog(arg + ": Unknown Option", self.LGEREX)
         elif not self.table:
            self.table = arg
         else:
            self.pglog(arg + ": one table name at a time", self.LGEREX)
      if not self.table:
         print("Usage: fillcountry TableName\n")
         sys.exit(0)
      elif self.table not in self.tables:
         self.pglog("{}: table name must be ({})".format(self.table, '|'.join(self.tables)), self.LGEREX)
      self.cmdlog("fillcountry {}".format(' '.join(argv)))

   # function to start actions
   def start_actions(self):
      self.dssdb_dbname()
      self.process_countries()

   # fill country info
   def process_countries(self):
      pgrecs = self.pgmget(self.table, "email", "country IS NULL", self.LOGWRN)
      cntall = len(pgrecs['email']) if pgrecs else 0
      self.pglog("Set {} record(s) for missing country in table {}".format(cntall, self.table), self.LOGWRN)
      if not cntall: return
      cntmod = 0
      for i in range(cntall):
         if i and (i % 500) == 0:
            self.pglog("{}/{} Records modified/processed".format(cntmod, i), self.WARNLG)
         email = pgrecs['email'][i]
         record = {'country' : self.email_to_country(email)}
         cntmod += self.pgupdt(self.table, record, "email = '{}' AND country IS NULL".format(email), self.LOGWRN)
      self.pglog("{} Record(s) modified in table '{}'".format(cntmod, self.table), self.LOGWRN)

# main function to excecute this script
def main():
   object = FillCountry()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
