#!/usr/bin/env python3
###############################################################################
#     Title : fillendtime
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 04/08/2024
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-17 convert to class FillEndTime
#   Purpose : python program to fill field dlupdt.endtime from enddate/endhour
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import sys
from rda_python_common.pg_util import PgUtil

class FillEndTime(PgUtil):

   def __init(self):
      super().__init__()
      self.DSIDS = []    # empty for all datasets

   # function to read parameters
   def read_parameters(self):
      argv = sys.argv[1:]
      for arg in argv:
         if arg == "-b":
            self.PGLOG['BCKGRND'] = 1
         else:
            self.DSIDS.append(PgUtil.format_dataset_id(arg))

   # function to start actions
   def start_actions(self):
      self.dssdb_dbname()
      if self.DSIDS:
         for dsid in self.DSIDS:
            self.fill_endtime(dsid)
      else:
         self.fill_endtime()

   # Fill endtime in table dssdb.dlupdt
   def fill_endtime(self, dsid = None):
      cnd = "dsid = '{}' AND ".format(dsid) if dsid else ''
      cnd += 'enddate <> NULL ORDER BY dsid, lindex'
      pgrecs = self.pgmget('dlupdt', 'lindex, dsid, enddate, endhour', cnd)
      cnt = len(pgrecs['lindex']) if pgrecs else 0
      dsids = []
      for i in range(cnt):
         lidx = pgrecs['lindex'][i]
         edate = pgrecs['enddate'][i]
         ehour = pgrecs['endhour'][i]
         dsid = pgrecs['dsid'][i]
         if dsid not in dsids: dsids.append(dsid)
         if ehour is None: ehour = 23
         etime = "{} {}:59:59".format(edate, ehour)
         self.pgexec("UPDATE dlupdt SET endtime = '{}' WHERE lindex = {}".format(etime, lidx), self.LGEREX)
      s = 's' if cnt > 1 else ''
      dscnt = len(dsids)
      dsstr = dsids[0] if dscnt == 1 else '{} datasets'.format(dscnt)
      self.pglog("{}: {} records updated for dssdb.dlupdt.endtime".format(dsstr, cnt, s), self.LOGWRN)

# main function to excecute this script
def main():
   object = FillEndTime()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
