##!/usr/bin/env python3
###############################################################################
#     Title : fillglobususage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/11/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-17 convert to FillGlobusUsage
#   Purpose : python program to retrieve info from Globus logs 
#             and fill table wusages in PostgreSQL database dssdb.
#    Github : https://github.com/NCAR/rda-pythn-metrics.git
###############################################################################
import sys
import re
import glob
from os import path as op
from rda_python_common.pg_file import PgFile
from rda_python_common.pg_split import PgSplit
from .pg_ipinfo import PgIPInfo

class FillGlobusUsage(PgIPInfo, PgSplit, PgFile):

   def __init__(self):
      super().__init()
      self.USAGE = {
         'PGTBL'  : "wusage",
         'GBSDIR' : self.PGLOG["GDEXWORK"] + "/logs/gridftp/",
         'GBSLOG' : "access_log_gridftp0{}_{}",
      }
      self.logfiles = []
      self.datelimits = [None, None]
      self.params = []  # array of input values
      self.option = self.cmdstr = None

   # function to red paramters
   def read_parameters(self):
      argv = sys.argv[1:]
      for arg in argv:
         ms = re.match(r'^-(b|d|f|p|N)$', arg)
         if ms:
            opt = ms.group(1)
            if opt == 'b':
               self.PGLOG['BCKGRND'] = 1
            elif self.option:
               self.pglog("{}: Option -{} is present already".format(arg, self.option), self.LGWNEX)
            else:
               self.option = opt
         elif re.match(r'^-', arg):
            self.pglog(arg + ": Invalid Option", self.LGWNEX)
         elif self.option:
            self.params.append(arg)
         else:
            self.pglog(arg + ": Invalid Parameter", self.LGWNEX)
      if not (self.option and self.params): self.show_usage('fillglobususage')
      self.cmdstr = "fillglobususage {}".format(' '.join(argv))
      self.cmdlog(self.cmdstr)
   
   # function to start actions
   def start_actions(self):
      self.dssdb_dbname()
      self.change_local_directory(self.USAGE['GBSDIR'])
      self.get_log_file_names()
      if self.logfiles:
         self.fill_globus_usages()
      else:
         self.pglog("No log file found for given command: " + self.cmdstr, self.LOGWRN)
      self.pglog(None, self.LOGWRN)
   
   # get the log file dates 
   def get_log_file_names(self):
      if self.option == 'f':
         self.logfiles = self.params
      elif self.option == 'd':
         for pdate in self.params:
            fdate = self.format_date(pdate, 'MMDDYYYY')
            fname = self.USAGE['GBSLOG'].format('?', fdate)
            fnames = glob.glob(fname)
            if fnames: self.logfiles.extend(sorted(fnames))
      else:
         if self.option == 'N':
            edate = self.curdate()
            pdate = self.datelimits[0] = self.adddate(edate, 0, 0, -int(self.params[0]))
         else:
            pdate = self.datelimits[0] = self.params[0]
            if len(self.params) > 1:
               edate = self.datelimits[1] = self.params[1]
            else:
               edate = self.curdate()
         while pdate <= edate:
            fdate = self.format_date(pdate, 'MMDDYYYY')
            fname = self.USAGE['GBSLOG'].format('?', fdate)
            fnames = glob.glob(fname)
            if fnames: self.logfiles.extend(sorted(fnames))
            pdate = self.adddate(pdate, 0, 0, 1)
   
   # Fill Globus usages into table dssdb.globususage of DSS PostgreSQL database from globus access logs
   def fill_globus_usages(self):
      cntall = addall = 0
      fcnt = len(self.logfiles)
      for logfile in self.logfiles:
         if not op.isfile(logfile):
            self.pglog("{}: Not exists for Gathering Globus usage".format(logfile), self.LOGWRN)
            continue
         self.pglog("Gathering usage info from {} at {}".format(logfile, self.current_datetime()), self.LOGWRN)
         globus = self.open_local_file(logfile)
         if not globus: continue
         ptime = ''
         record = {}
         cntadd = entcnt = 0
         pkey = None
         while True:
            line = globus.readline()
            if not line: break
            entcnt += 1
            if entcnt%10000 == 0:
               self.pglog("{}: {}/{} Globus log entries processed/records added".format(logfile, entcnt, cntadd), self.WARNLG)
            ms = re.match(r'^([\d\.]+)\s.*\s+\[(\S+).*"GET\s+/(ds\d\d\d\.\d|[a-z]\d{6})/(\S+)\s.*\s(200|206)\s+(\d+)\s+"(\S+)"\s+"(.+)"$', line)
            if not ms: continue
            size = int(ms.group(6))
            if size < 100: continue  # ignore small files
            ip = ms.group(1)
            dsid = self.format_dataset_id(ms.group(3))
            wfile = ms.group(4)
            stat = ms.group(5)
            sline = ms.group(7)
            engine = ms.group(8)
            (year, quarter, date, time) = self.get_record_date_time(ms.group(2))
            if self.datelimits[0] and date < self.datelimits[0]: continue
            if self.datelimits[1] and date > self.datelimits[1]: continue
            locflag = 'O' if re.match(r'^https://stratus\.', sline) else 'G'
            idx = wfile.find('?')
            if idx > -1: wfile = wfile[:idx]
            moff = engine.find('/')
            if moff > 0:
               if moff > 20: moff = 20
               method = engine[0:moff].upper()
            else:
               method = "WEB"
            key = "{}:{}:{}".format(ip, dsid, wfile) if stat == '206' else None
            if record:
               if key == pkey:
                  record['size'] += size
                  continue
               cntadd += self.add_file_usage(year, record)
            record = {'ip' : ip, 'dsid' : dsid, 'wfile' : wfile, 'date' : date,
                      'time' : time, 'quarter' : quarter, 'size' : size,
                      'locflag' : locflag, 'method' : method}
            pkey = key
            if not pkey:
               cntadd += self.add_file_usage(year, record)
               record = None
         if record: cntadd += self.add_file_usage(year, record)
         globus.close()
         cntall += entcnt
         addall += cntadd
         self.pglog("{} Globus usage records added for {} entries at {}".format(addall, cntall, self.current_datetime()), self.LOGWRN)
   
   # get date and time from log entry
   def get_record_date_time(self, ctime):
      ms = re.search(r'^(\d+)/(\w+)/(\d+):(\d+:\d+:\d+)$', ctime)
      if ms:
         d = int(ms.group(1))
         m = self.get_month(ms.group(2))
         y = ms.group(3)
         t = ms.group(4)
         q = 1 + int((m-1)/3)
         return (y, q, "{}-{:02}-{:02}".format(y, m, d), t)
      else:
         self.pglog(ctime + ": Invalid date/time format", self.LGEREX)
   
   # Fill usage of a single online data file into table dssdb.wusage of DSS PostgreSQL database
   def add_file_usage(self, year, logrec):
      pgrec = self.get_wfile_wid(logrec['dsid'], logrec['wfile'])
      if not pgrec: return 0
      table = "{}_{}".format(self.USAGE['PGTBL'], year)
      cond = "wid = {} AND method = '{}' AND date_read = '{}' AND time_read = '{}'".format(pgrec['wid'], logrec['method'], logrec['date'], logrec['time'])
      if self.pgget(table, "", cond, self.LOGWRN): return 0
      wurec =  self.get_wuser_record(logrec['ip'], logrec['date'])
      if not wurec: return 0
      record = {'wid' : pgrec['wid'], 'dsid' : pgrec['dsid']}
      record['wuid_read'] = wurec['wuid']
      record['date_read'] = logrec['date']
      record['time_read'] = logrec['time']
      record['size_read'] = logrec['size']
      record['method'] = logrec['method']
      record['locflag'] = logrec['locflag']
      record['ip'] = logrec['ip']
      record['quarter'] = logrec['quarter']
      if self.add_to_allusage(year, logrec, wurec):
         return self.add_yearly_wusage(year, record)
      else:
         return 0

   # add usage to allusage tables   
   def add_to_allusage(self, year, logrec, wurec):
      pgrec = {'email' : wurec['email'], 'org_type' : wurec['org_type'],
               'country' : wurec['country'], 'region' : wurec['region']}
      pgrec['dsid'] = logrec['dsid']
      pgrec['date'] = logrec['date']
      pgrec['quarter'] = logrec['quarter']
      pgrec['time'] = logrec['time']
      pgrec['size'] = logrec['size']
      pgrec['method'] = logrec['method']
      pgrec['ip'] = logrec['ip']
      pgrec['source'] = 'W'
      return self.add_yearly_allusage(year, pgrec)

   # return wfile.wid upon success, 0 otherwise
   def get_wfile_wid(self, dsid, wfile):
      wfcond = "wfile = '{}'".format(wfile) 
      pgrec = self.pgget_wfile(dsid, "*", wfcond)
      if pgrec:
         pgrec['dsid'] = dsid
      else:
         pgrec = self.pgget("wfile_delete", "*", "{} AND dsid = '{}'".format(wfcond, dsid))
         if not pgrec:
            pgrec = self.pgget("wmove", "wid, dsid", wfcond)
            if pgrec:
               pgrec = self.pgget_wfile(pgrec['dsid'], "*", "wid = {}".format(pgrec['wid']))
               if pgrec: pgrec['dsid'] = dsid
      return pgrec

# main function to excecute this script
def main():
   object = FillGlobusUsage()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
