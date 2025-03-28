#!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillendtime
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 04/08/2024
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to fill field dlupdt.endtime from enddate/endhour
# 
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
###############################################################################
#
import sys
import re
import glob
from os import path as op
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgFile
from rda_python_common import PgDBI
from . import PgIPInfo

# the define options for gathering ipinfo data
MONTH = 0x02  # fix data usages for given months
YEARS = 0x04  # fix data usages for given years
NDAYS = 0x08  # fix data usages in recent number of days
MULTI = (MONTH|YEARS)
SINGL = (NDAYS)

IPINFO = {
   'USGTBL'  : ['ipinfo', 'allusage', 'tdsusage'],
   'CDATE' : PgUtil.curdate(),
}

#
# main function to run this program
#
def main():

   dsids = []    # empty for all datasets
   argv = sys.argv[1:]
   option = 0

   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
      else:
         dsids.append(PgUtil.format_dataset_id(arg))

   PgDBI.dssdb_dbname()

   if dsids:
      for dsid in dsids:
         fill_endtime(dsid)
   else:
      fill_endtime()
   sys.exit(0)



#
# Fill endtime in table dssdb.dlupdt
#
def fill_endtime(dsid = None):

   dsids = []
   cnd = "dsid = '{}' AND ".format(dsid) if dsid else ''
   cnd += 'enddate <> NULL ORDER BY dsid, lindex'
   pgrecs = PgDBI.pgmget('dlupdt', 'lindex, dsid, enddate, endhour', cnd)

   cnt = len(pgrecs['lindex']) if pgrecs else 0
   for i in range(cnt):
      lidx = pgrecs['lindex'][i]
      edate = pgrecs['enddate'][i]
      ehour = pgrecs['endhour'][i]
      dsid = pgrecs['dsid'][i]
      if dsid not in dsids: dsids.append()
      if ehour is None: ehour = 23
      etime = "{} {}:59:59".format(edate, ehour)
      PgDBI.pgexec("UPDATE dlupdt SET endtime = '{}' WHERE lindex = {}".format(etime, lidx), PgLOG.LGEREX)

   s = 's' if cnt > 1 else ''
   dscnt = len(dsids)
   dsstr = dsids[0] if dscnt == 1 else '{} datasets'.format(dscnt)
   PgLOG.pglog("{}: {} records updated for dssdb.dlupdt.endtime".format(dsstr, cnt, s), PgLOG.LOGWRN)

#
# call main() to start program
#
if __name__ == "__main__": main()
