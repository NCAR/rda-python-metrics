#!/usr/bin/env python3
###############################################################################
#     Title : fillrdadb
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 04/07/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-17 convert to class FillRDADB
#   Purpose : python program to retrieve info from data logs, and fill tables
#             in PostgreSQL database.schema rdadb.dssdb
#    Github : https://github.com/NCAR/rda-pythn-metrics.git
###############################################################################
import sys
import re
from rda_python_common.pg_util import PgUtil

class FillRDADB(PgUtil):

   def __init__(self):
      super().__init__()
      # the define options for gathering web online file usage, one at a time
      self.DATES = 0x01  # get web file usages for given dates
      self.MONTH = 0x02  # fet web file usages for given months
      self.YEARS = 0x04  # get web file usages for given years
      self.NDAYS = 0x08  # get web file usages in recent number of days 
      self.CLNFL = 0x10  # clean unused file only
      self.MASKS = (self.MONTH|self.YEARS|self.DATES|self.NDAYS)
      self.RDADB = {
         'OPTION' : 0,
         'OPTVAL' : '',
         'DOMAIL' : 1,
         'BCKGRND' : ''
      }
      self.params = []   # array of input values

# function to read parameters
def read_paramers(self):
   argv = sys.argv[1:]
   for arg in argv:
      if arg == "-b":
         self.PGLOG['BCKGRND'] = "-b"
         self.RDADB['BCKGRND'] = " -b"
      elif arg == "-n":
         self.RDADB['DOMAIL'] = 0
         self.PGLOG['LOGMASK'] &= ~(self.EMLALL)
      elif re.match(r'^-[cdmNy]$', arg) and not self.RDADB['OPTVAL']:
         self.RDADB['OPTVAL'] = arg
         if arg == "-c":
            self.RDADB['OPTION'] |= self.CLNFL
         elif arg == "-d":
            self.RDADB['OPTION'] |= self.DATES
         elif arg == "-m":
            self.RDADB['OPTION'] |= self.MONTH
         elif arg == "-y":
            self.RDADB['OPTION'] |= self.YEARS
         elif arg == "-N":
            self.RDADB['OPTION'] |= self.NDAYS
      elif re.match(r'^-.*', arg):
         self.pglog(arg + ": Invalid Option", self.LGWNEX)
      elif self.RDADB['OPTION']&self.MASKS:
         self.params.append(arg)
      else:
         self.pglog(arg + ": Invalid Parameter", self.LGWNEX)
   if not self.RDADB['OPTION'] or (self.RDADB['OPTION']&self.MASKS and not self.params):
      self.show_usage('fillrdadb')
   self.cmdlog("fillrdadb {}".format(' '.join(argv)))

# function to start actions
def start_actions(self):
   self.dssdb_dbname()
   if self.RDADB['OPTION']&self.CLNFL: # clean unused file only
      self.clean_unused_files()
   elif self.RDADB['OPTION']&self.MASKS:
      self.fill_rdadb(self.RDADB['OPTVAL'])

# Fill self.RDADB info for given condition
def fill_rdadb(self, option):
   filecond = '{} {}'.format(option, ' '.join(self.params))
   self.pglog("Filling self.RDADB info for '{}' at {}".format(filecond, self.current_datetime()), self.LOGWRN)
   # fill available custom OPeNDAP usages
   self.pgsystem("fillcodusage {} {}".format(self.RDADB['BCKGRND'], filecond), self.LGWNEM, 5)
   # fill available globus web data usages
   self.pgsystem("fillglobususage {} {}".format(self.RDADB['BCKGRND'], filecond), self.LGWNEM, 5)
   # fill available AWS web data usages
   self.pgsystem("fillawsusage {} {}".format(self.RDADB['BCKGRND'], filecond), self.LGWNEM, 5)
   # fill available OSDF web data usages
   self.pgsystem("fillosdfusage {} {}".format(self.RDADB['BCKGRND'], filecond), self.LGWNEM, 5)
   if self.RDADB['DOMAIL']: self.send_email_notice()
   self.pglog("End Filling self.RDADB info at {}".format(self.current_datetime()), self.LGWNEM)

# clean unused MSS and Web files
def clean_unused_files(self):
   self.pglog("Check and clean deleted Web files that never been used at {}".format(self.current_datetime()), self.LOGWRN)
   pgrecs = self.pgmget("wfile", "wid", "status = 'D'", self.LGWNEX)
   allcnt = len(pgrecs['wid']) if pgrecs else 0
   self.pglog("{} record(s) retrieved from Table 'wfile' at {}".format(allcnt, self.current_datetime()), self.LOGWRN)
   procnt = delcnt = 0
   if allcnt:
      fcond = r"wid = {} AND org_type <> 'DSS' AND wuid_read = wuid"
      for fid in pgrecs['wid']:
         procnt += 1
         if procnt%5000 == 0:
            self.pglog("{}/{} record(s) processed/removed from Table 'wfile'".format(procnt, delcnt), self.WARNLG)
         if not self.pgget("wusage, wuser", "", fcond.format(fid), self.LGWNEX):
            # deleted web file never been used
            delcnt += self.pgdel("wfile", "wid = {}".format(fid), self.LGWNEX)
   self.pglog("{} record(s) removed from Table 'wfile' at {}".format(delcnt, self.current_datetime()), self.LOGWRN)

# email notice of job done
def send_email_notice(self):
   msg = ("Hi All,\n\nself.RDADB weekly data usage gathering is done at {}.\n\n".format(self.current_datetime()) +
          "Please Let me know if you notice any problem.\n\nThanks,\n\nHua\n")
   pgrecs = self.pgmget("dssgrp", "logname", "email_flag = 'Y'", self.LGWNEX)
   if pgrecs:
      receiver = ""
      for logname in pgrecs['logname']:
         if receiver: receiver += ', '
         receiver += (logname + "@ucar.edu")
      self.send_email("self.RDADB Weekly Data Usage Gathered on " + self.curdate(), receiver, msg)

# main function to excecute this script
def main():
   object = FillRDADB()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
