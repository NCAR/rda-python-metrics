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
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import sys
import re
from rda_python_common.pg_util import PgUtil
from rda_python_common.pg_dbi import PgDBI

class FillRDADB(PgUtil, PgDBI):

   """Retrieve info from data logs and fill tables in PostgreSQL database rdadb."""

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
         'BCKGRND' : '',
         'BACKDAYS' : 0   # days to reach back for missed dates, set by -B
      }
      # the usage table and its date field, per command to reprocess with -d
      self.BACKFILL = {
         'fillosdfusage'   : ('osdfusage', 'date'),
         'fillawsusage'    : ('awsusage', 'date'),
         'fillglobususage' : ('wusage', 'date_read'),
         'fillcodusage'    : ('codusage', 'date')
      }
      self.params = []   # array of input values

   def read_parameters(self):
      """Function to read parameters."""
      argv = sys.argv[1:]
      backopt = 0   # the value after -B is the number of days to reach back
      for arg in argv:
         if arg == "-B":
            backopt = 1
         elif arg == "-b":
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
         elif backopt:
            if not re.match(r'^\d+$', arg):
               self.pglog(arg + ": Number of days back must be a whole number", self.LGWNEX)
            self.RDADB['BACKDAYS'] = int(arg)
            backopt = 0
         elif self.RDADB['OPTION']&self.MASKS:
            self.params.append(arg)
         else:
            self.pglog(arg + ": Invalid Parameter", self.LGWNEX)
      if backopt: self.pglog("-B: Miss number of days to reach back", self.LGWNEX)
      if not self.RDADB['OPTION'] or (self.RDADB['OPTION']&self.MASKS and not self.params):
         self.show_usage('fillrdadb')
      if self.RDADB['BACKDAYS'] and not self.RDADB['OPTION']&self.NDAYS:
         self.pglog("-B: Ignored, reaching back for missed dates needs -N", self.LOGWRN)
      self.cmdlog("fillrdadb {}".format(' '.join(argv)))
   
   def start_actions(self):
      """Function to start actions."""
      self.dssdb_dbname()
      if self.RDADB['OPTION']&self.CLNFL: # clean unused file only
         self.clean_unused_files()
      elif self.RDADB['OPTION']&self.MASKS:
         self.fill_rdadb(self.RDADB['OPTVAL'])
   
   def fill_rdadb(self, option):
      """Fill self.RDADB info for given condition."""
      filecond = '{} {}'.format(option, ' '.join(self.params))
      self.pglog("Filling RDADB info for '{}' at {}".format(filecond, self.current_datetime()), self.LOGWRN)
      # fill available custom OPeNDAP usages
      self.pgsystem("fillcodusage {} {}".format(self.RDADB['BCKGRND'], filecond), self.LGWNEM, 5)
      # fill available globus web data usages
      self.pgsystem("fillglobususage {} {}".format(self.RDADB['BCKGRND'], filecond), self.LGWNEM, 5)
      # fill available AWS web data usages
      self.pgsystem("fillawsusage {} {}".format(self.RDADB['BCKGRND'], filecond), self.LGWNEM, 5)
      # fill available OSDF web data usages
      self.pgsystem("fillosdfusage {} {}".format(self.RDADB['BCKGRND'], filecond), self.LGWNEM, 5)
      # the -N window is the only thing that reaches a log file again, so one
      # published after its date leaves the window is never asked for; -B catches those
      if self.RDADB['BACKDAYS'] and self.RDADB['OPTION']&self.NDAYS:
         self.backfill_missed_dates(int(self.params[0]))
      if self.RDADB['DOMAIL']: self.send_email_notice()
      self.pglog("End Filling RDADB info at {}".format(self.current_datetime()), self.LGWNEM)
   
   def backfill_missed_dates(self, ndays):
      """Reprocess the dates before the -N window that still hold no usage record.

      Only runs when -B gave a number of days to reach back. A log file is
      sometimes published after its date has slid out of the -N window, and
      nothing fetches it again, so the date stays empty however often the job
      runs. Asking each usage table which dates it is missing keeps those dates
      being retried until their log shows up, as far back as -B allows.

      A date whose log holds no usable entry simply keeps being offered until it
      ages out past BACKDAYS. That is deliberate: the obvious alternative, taking
      an already processed log as proof of coverage, would silently write off the
      dates left empty by a run that died partway.
      """
      edate = self.adddate(self.curdate(), 0, 0, -ndays)
      bdate = self.adddate(self.curdate(), 0, 0, -self.RDADB['BACKDAYS'])
      if bdate >= edate: return
      for cmd in self.BACKFILL:
         (tbname, datefld) = self.BACKFILL[cmd]
         dates = self.get_unfilled_dates(tbname, datefld, bdate, edate)
         if not dates: continue
         self.pglog("{}: {} date(s) between {} and {} hold no usage, reprocessing".format(
                    cmd, len(dates), bdate, edate), self.LOGWRN)
         self.pgsystem("{} {} -d {}".format(cmd, self.RDADB['BCKGRND'], ' '.join(dates)), self.LGWNEM, 5)

   def get_unfilled_dates(self, tbname, datefld, bdate, edate):
      """Get the dates in [bdate, edate) holding no record in a usage table."""
      filled = set()
      for table in self.get_usage_tables(tbname, bdate, edate):
         cnd = "{} >= '{}' AND {} < '{}'".format(datefld, bdate, datefld, edate)
         pgrecs = self.pgmget(table, 'DISTINCT ' + datefld, cnd, self.LOGWRN)
         if pgrecs and datefld in pgrecs:
            filled.update(str(d) for d in pgrecs[datefld])
      dates = []
      pdate = bdate
      while pdate < edate:
         if pdate not in filled: dates.append(pdate)
         pdate = self.adddate(pdate, 0, 0, 1)
      return dates

   def get_usage_tables(self, tbname, bdate, edate):
      """Get the existing table names for a usage table, one per year if split."""
      tables = []
      for year in range(int(bdate[0:4]), int(edate[0:4]) + 1):
         table = "{}_{}".format(tbname, year)
         if self.pgget('information_schema.tables', 'table_name',
                       "table_name = '{}'".format(table), self.LOGWRN):
            tables.append(table)
      return tables if tables else [tbname]

   def clean_unused_files(self):
      """Clean unused MSS and Web files."""
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
   
   def send_email_notice(self):
      """Email notice of job done."""
      msg = ("Hi All,\n\nRDADB weekly data usage gathering is done at {}.\n\n".format(self.current_datetime()) +
             "Please Let me know if you notice any problem.\n\nThanks,\n\nHua\n")
      pgrecs = self.pgmget("dssgrp", "logname", "email_flag = 'Y'", self.LGWNEX)
      if pgrecs:
         receiver = ""
         for logname in pgrecs['logname']:
            if receiver: receiver += ', '
            receiver += (logname + "@ucar.edu")
         self.send_email("RDADB Weekly Data Usage Gathered on " + self.curdate(), receiver, msg)

# main function to execute this script
def main():
   object = FillRDADB()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
