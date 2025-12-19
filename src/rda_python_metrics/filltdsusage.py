#!/usr/bin/env python3
###############################################################################
#     Title : filltdsusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/11/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-17 convert to class FillTDSUsage
#   Purpose : python program to retrieve info from TDS logs 
#             and fill table tdsusage in PostgreSQL database dssdb.
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import sys
import re
import glob
from os import path as op
from rda_python_common.pg_file import PgFile
from .pg_ipinfo import PgIPInfo

class FillTDSUsage(PgIPInfo, PgFile):

   def __init__(self):
      super().__init__()
      self.USAGE = {
         'OPTION' : 0,
         'PGTBL'  : "tdsusage",
         'GITDIR' : self.PGLOG["GDEXWORK"] + "/zji/tdslogs/tds-logs",
         'GITGET' : 'git pull',
         'TDSDIR' : self.PGLOG["GDEXWORK"] + "/zji/tdslogs/work",
         'GZFILE' : '../tds-logs/logs/{}.gz',
         'TDSGET' : 'gunzip -c {} > {}',
         'TDSLOG' : "localhost_access_log.{}.txt"   # {} = YYYY-MM-DD
      }
      self.params = []  # array of input values
      self.option = None
      self.logfiles = []

# function to read parameters
def read_parameters(self):
   argv = sys.argv[1:]
   for arg in argv:
      ms = re.match(r'^-(b|d|p|N)$', arg)
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
   if not (self.option and self.params): self.show_usage('filltdsusage')
   cmdstr = "filltdsusage {}".format(' '.join(argv))
   self.cmdlog(cmdstr)

   # function to start actions
   def start_actions(self):
      pull_github_repo()
      self.dssdb_dbname()
      PgFile.change_local_directory(self.USAGE['TDSDIR'])
      get_log_file_names()
      if self.logfiles:
         fill_tds_usages()
      else:
         self.pglog("No log file found for given command: " + cmdstr, self.LOGWRN)
      self.pglog(None, self.LOGWRN)

   # get the log file dates 
   def get_log_file_names(self):
      if self.option == 'd':
         for pdate in self.params:
            self.logfiles.append(self.USAGE['TDSLOG'].format(pdate))
      else:
         if self.option == 'N':
            edate = self.curdate()
            pdate = self.adddate(edate, 0, 0, -int(self.params[0]))
         else:
            pdate = self.params[0]
            if len(self.params) > 1:
               edate = self.params[1]
            else:
               edate = self.curdate()
         while pdate <= edate:
            self.logfiles.append(self.USAGE['TDSLOG'].format(pdate))
            pdate = self.adddate(pdate, 0, 0, 1)

   # git pull the github repo
   def pull_github_repo(self):
      PgFile.change_local_directory(self.USAGE['GITDIR'])
      self.pgsystem(self.USAGE['GITGET'], 5, self.LOGWRN)

   # Fill TDS usages into table dssdb.tdsusage from tds access logs
   def fill_tds_usages(self):
      year = cntall = addall = 0
      for logfile in self.logfiles:
         linfo = PgFile.check_local_file(logfile)
         if not linfo:
            gzfile = self.USAGE['GZFILE'].format(logfile)
            linfo = PgFile.check_local_file(gzfile)
            if not linfo:
               self.pglog("{}: Not exists for Gathering TDS usage".format(gzfile), self.LOGWRN)
               continue
            self.pgsystem(self.USAGE['TDSGET'].format(gzfile, logfile), 5, self.LOGWRN)
            linfo = PgFile.check_local_file(logfile)
            if not linfo:
               self.pglog("{}: Error gunzip TDS usage".format(gzfile), self.LGEREX)
         self.pglog("{}: Gathering TDS usage at {}".format(logfile, self.current_datetime()), self.LOGWRN)
         tds = PgFile.open_local_file(logfile)
         if not tds: continue
         records = {}
         cntadd = entcnt = 0
         while True:
            line = tds.readline()
            if not line: break
            entcnt += 1
            if entcnt%20000 == 0:
               cnt = len(records)
               self.pglog("{}/{} TDS log entries processed/records to add".format(entcnt, cnt), self.WARNLG)
            ms = re.search(r'(/thredds/catalog|\sGooglebot/)', line)
            if ms: continue
            ms = re.search(r'/thredds/\S+\.(png|jpg|gif|css|htm)', line)
            if ms: continue
            ms = re.match(r'^([\d\.]+)\s.*\s(-|\S+@\S+)\s+\[(\S+).*/thredds/(\w+)(/|/grid/)(aggregations|files).*/(ds\d\d\d.\d|[a-z]\d{6})/.*\s200\s+(\d+)(.*)$', line)
            if not ms: continue
            ip = ms.group(1)
            email = ms.group(2)
            (date, time) = self.get_record_date_time(ms.group(3))
            if not date: continue
            method = ms.group(4)
            etype = ms.group(6)[0].upper()
            dsid = self.format_dataset_id(ms.group(7))
            size = int(ms.group(8))
            ebuf = ms.group(9)
            ms = re.search(r' "(\w+.*\S+)" ', ebuf)
            engine = ms.group(1) if ms else 'Unknown'
            iprec = self.set_ipinfo(ip)
            if not iprec: continue
            ip = iprec['ip']
            key = "{}:{}:{}:{}".format(ip, dsid, method, etype)
            if key in records:
               records[key]['size'] += size
               records[key]['fcount'] += 1
            else:
               records[key] = {'ip' : ip, 'email' : email, 'dsid' : dsid, 'time' : time, 'size' : size,
                              'fcount' : 1, 'method' : method, 'etype' : etype, 'engine' : engine}
         tds.close()
         if records: cntadd += self.add_usage_records(records, date)
         cntall += entcnt
         addall += cntadd
      self.pglog("{} TDS usage records added for {} entries at {}".format(addall, cntall, self.current_datetime()), self.LOGWRN)

   # get date and time ffrom log entry
   def get_record_date_time(self, ctime):
      ms = re.search(r'^(\d+)/(\w+)/(\d+):(\d+:\d+:\d+)$', ctime)
      if ms:
         d = int(ms.group(1))
         m = self.get_month(ms.group(2))
         y = ms.group(3)
         t = ms.group(4)
         return ("{}-{:02}-{:02}".format(y, m, d), t)
      else:
         self.pglog(f"{ctime}: Invalid time format", self.LGEREX)
         return (None, None)

   # add usage to table tdsusage
   def add_usage_records(self, records, date):
      quarter = cnt = 0
      year = None
      ms = re.search(r'(\d+)-(\d+)-', date)
      if ms:
         year = ms.group(1)
         quarter = 1 + int((int(ms.group(2)) - 1)/3)
      for key in records:
         record = records[key]
         cond = "date = '{}' AND time = '{}' AND ip = '{}' AND dsid = '{}'".format(date, record['time'], record['ip'], record['dsid'])
         if self.pgget(self.USAGE['PGTBL'], '', cond, self.LGEREX): continue
         email = None if record['email'] == '-' else record['email']
         wurec = self.get_wuser_record(record['ip'], date)
         if not wurec: continue
         record['ip'] = wurec['ip']    # in case generic ip
         record['org_type'] = wurec['org_type']
         record['country'] = wurec['country']
         record['region'] = wurec['region']
         record['email'] = 'unknown@' + wurec['hostname']
         record['quarter'] = quarter
         record['date'] = date
         if self.add_to_allusage(year, record):
            cnt += self.pgadd(self.USAGE['PGTBL'], record, self.LOGWRN)
      self.pglog("{}: {} TDS usage records added at {}".format(date, cnt, self.current_datetime()), self.LOGWRN)
      return cnt

   # add usage to table allusage
   def add_to_allusage(self, year, pgrec):
      record = {'method' : 'TDS', 'source' : 'T'}
      for fld in pgrec:
         if re.match(r'^(engine|method|etype|fcount)$', fld): continue
         record[fld] = pgrec[fld]
      return self.add_yearly_allusage(year, record)

# main function to excecute this script
def main():
   object = FillTDSUsage()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
