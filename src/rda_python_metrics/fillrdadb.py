#!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillrdadb
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 04/07/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to retrieve info from data logs, and fill tables
#             in PostgreSQL database.schema rdadb.dssdb
#
#    Github : https://github.com/NCAR/rda-pythn-metrics.git
#
###############################################################################
#
import sys
import re
from os import path as op
from rda_python_common import PgLOG
from rda_python_common import PgFile
from rda_python_common import PgUtil
from rda_python_common import PgDBI

# the define options for gathering web online file usage, one at a time
DATES = 0x01  # get web file usages for given dates
MONTH = 0x02  # fet web file usages for given months
YEARS = 0x04  # get web file usages for given years
NDAYS = 0x08  # get web file usages in recent number of days 
CLNFL = 0x10  # clean unused file only
MASKS = (MONTH|YEARS|DATES|NDAYS)

RDADB = {
   'OPTION' : 0,
   'OPTVAL' : '',
   'DOMAIL' : 1,
   'BCKGRND' : ''
}

#
# main function to run this program
#
def main():

   params = []   # array of input values
   argv = sys.argv[1:]
   bckflag = ''

   PgDBI.dssdb_dbname()
   
   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = "-b"
         RDADB['BCKGRND'] = " -b"
      elif arg == "-n":
         RDADB['DOMAIL'] = 0
         PgLOG.PGLOG['LOGMASK'] &= ~(PgLOG.EMLALL)
      elif re.match(r'^-[cdmNy]$', arg) and not RDADB['OPTVAL']:
         RDADB['OPTVAL'] = arg
         if arg == "-c":
            RDADB['OPTION'] |= CLNFL
         elif arg == "-d":
            RDADB['OPTION'] |= DATES
         elif arg == "-m":
            RDADB['OPTION'] |= MONTH
         elif arg == "-y":
            RDADB['OPTION'] |= YEARS
         elif arg == "-N":
            RDADB['OPTION'] |= NDAYS
         
      elif re.match(r'^-.*', arg):
         PgLOG.pglog(arg + ": Invalid Option", PgLOG.LGWNEX)
      elif RDADB['OPTION']&MASKS:
         params.append(arg)
      else:
         PgLOG.pglog(arg + ": Invalid Parameter", PgLOG.LGWNEX)

   if not RDADB['OPTION'] or (RDADB['OPTION']&MASKS and not params):
      PgLOG.show_usage('fillrdadb')
   PgDBI.dssdb_dbname()
   PgLOG.cmdlog("fillrdadb {}".format(' '.join(argv)))

   if RDADB['OPTION']&CLNFL: # clean unused file only
      clean_unused_files()
   elif RDADB['OPTION']&MASKS:
      fill_rdadb(RDADB['OPTVAL'], params)

   sys.exit(0)

#
# Fill RDADB info for given condition
#
def fill_rdadb(option, params):

   filecond = '{} {}'.format(option, ' '.join(params))
   PgLOG.pglog("Filling RDADB info for '{}' at {}".format(filecond, PgLOG.current_datetime()), PgLOG.LOGWRN)

   # fill available custom OPeNDAP usages
   PgLOG.pgsystem("fillcodusage {} {}".format(RDADB['BCKGRND'], filecond), PgLOG.LGWNEM, 5)
   # fill available globus web data usages
   PgLOG.pgsystem("fillglobususage {} {}".format(RDADB['BCKGRND'], filecond), PgLOG.LGWNEM, 5)
   # fill available AWS web data usages
   PgLOG.pgsystem("fillawsusage {} {}".format(RDADB['BCKGRND'], filecond), PgLOG.LGWNEM, 5)
   # fill available OSDF web data usages
   PgLOG.pgsystem("fillosdfusage {} {}".format(RDADB['BCKGRND'], filecond), PgLOG.LGWNEM, 5)

   if RDADB['DOMAIL']: send_email_notice()
   PgLOG.pglog("End Filling RDADB info at {}".format(PgLOG.current_datetime()), PgLOG.LGWNEM)

#
# clean unused MSS and Web files
#
def clean_unused_files():

   PgLOG.pglog("Check and clean deleted Web files that never been used at {}".format(PgLOG.current_datetime()), PgLOG.LOGWRN)
   pgrecs = PgDBI.pgmget("wfile", "wid", "status = 'D'", PgLOG.LGWNEX)
   
   allcnt = len(pgrecs['wid']) if pgrecs else 0
   PgLOG.pglog("{} record(s) retrieved from Table 'wfile' at {}".format(allcnt, PgLOG.current_datetime()), PgLOG.LOGWRN)
   procnt = delcnt = 0
   if allcnt:
      fcond = r"wid = {} AND org_type <> 'DSS' AND wuid_read = wuid"
      for fid in pgrecs['wid']:
         procnt += 1
         if procnt%5000 == 0:
            PgLOG.pglog("{}/{} record(s) processed/removed from Table 'wfile'".format(procnt, delcnt), PgLOG.WARNLG)
         if not PgDBI.pgget("wusage, wuser", "", fcond.format(fid), PgLOG.LGWNEX):
            # deleted web file never been used
            delcnt += PgDBI.pgdel("wfile", "wid = {}".format(fid), PgLOG.LGWNEX)

   PgLOG.pglog("{} record(s) removed from Table 'wfile' at {}".format(delcnt, PgLOG.current_datetime()), PgLOG.LOGWRN)

#
# email notice of job done
#
def send_email_notice():

   msg = ("Hi All,\n\nRDADB weekly data usage gathering is done at {}.\n\n".format(PgLOG.current_datetime()) +
          "Please Let me know if you notice any problem.\n\nThanks,\n\nHua\n")
   pgrecs = PgDBI.pgmget("dssgrp", "logname", "email_flag = 'Y'", PgLOG.LGWNEX)
   if pgrecs:
      receiver = ""
      for logname in pgrecs['logname']:
         if receiver: receiver += ', '
         receiver += (logname + "@ucar.edu")

      ret = PgLOG.send_email("RDADB Weekly Data Usage Gathered on " + PgUtil.curdate(), receiver, msg)
      if ret: PgLOG.pglog(ret, PgLOG.LOGWRN)

#
# call main() to start program
#
if __name__ == "__main__": main()
