#!/usr/bin/env python3
###############################################################################
#     Title : fillcodusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/11/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-17 convert to class FillCODEUsage
#   Purpose : python program to retrieve info from web logs 
#             and fill table codusage in PostgreSQL database dssdb.
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import sys
import re
import glob
from os import path as op
from .pg_ipinfo import PgIPInfo

class FillCODUsage(PgIPInfo):

   def __init__(self):
      super().__init()
      # the define options for gathering COD data usage, one at a time
      self.MONTH = 0x02  # fet COD data usages for given months
      self.YEARS = 0x04  # get COD data usages for given years
      self.NDAYS = 0x08  # get COD data usages in recent number of days 
      self.FILES = 0x10  # get given file names
      self.GTALL = 0x20  # get all data files of read
      self.MASKS = (self.MONTH|self.YEARS|self.NDAYS|self.FILES)
      self.USAGE = {
         'OPTION' : 0,
         'PGTBL'  : "codusage",
         'WEBLOG' : "/var/log/httpd",
      }
      self.USERS = {}  # cache user info for aid
      self.datelimit = ''
      self.params = []  # array of input values

   # function to readparameters
   def read_parameters(self):
      argv = sys.argv[1:]
      for arg in argv:
         if arg == "-b":
            self.PGLOG['BCKGRND'] = 1
         elif re.match(r'^-[afmNy]$', arg) and self.USAGE['OPTION'] == 0:
            if arg == "-a":
               self.USAGE['OPTION'] = self.GTALL
               self.params = ['']
            elif arg == "-f":
               self.USAGE['OPTION'] = self.FILES
            elif arg == "-m":
               self.USAGE['OPTION'] = self.MONTH
            elif arg == "-y":
               self.USAGE['OPTION'] = self.YEARS
            elif arg == "-N":
               self.USAGE['OPTION'] = self.NDAYS
         elif re.match(r'^-', arg):
            self.pglog(arg + ": Invalid Option", self.LGWNEX)
         elif self.USAGE['OPTION']&self.MASKS:
            self.params.append(arg)
         else:
            self.pglog(arg + ": Invalid Parameter", self.LGWNEX)
      if not (self.USAGE['OPTION'] and self.params): self.show_usage('fillcodusage')
      self.dssdb_dbname()
      self.cmdlog("fillcodusage {}".format(' '.join(argv)))

   # function to start actions
   def start_actions(self):   
      if self.USAGE['OPTION']&self.NDAYS:
         curdate = self.curdate()
         self.datelimit = self.adddate(curdate, 0, 0, -int(self.params[0]))
         self.USAGE['OPTION'] = self.MONTH
         self.params = []
         while curdate >= self.datelimit:
            (year, month, day) = curdate.split('-')
            self.params.append("{}-{}".format(year, month))
            curdate = self.adddate(curdate, 0, 0, -int(day))
      self.fill_cod_usages(self.USAGE['OPTION'], self.params)
      self.pglog(None, self.LOGWRN|self.SNDEML)  # send email out if any

   # Fill COD usages into table dssdb.codusage of DSS PostgreSQL database from cod access logs
   def fill_cod_usages(self, option, inputs):
      cntall = cntadd = 0
      for input in inputs:
         # get log file names
         if option&self.FILES:
            logfiles = [input]
         elif option&self.MONTH:
            tms = input.split('-')
            yrmn = "{}{:02}".format(tms[0], int(tms[1]))
            logfiles = ["{}/{}/access_log".format(self.USAGE['WEBLOG'], yrmn)]
         else: # self.GTALL | self.YEARS
            yrmn = input + "*"
            logfiles = glob.glob("{}/{}/access_log".format(self.USAGE['WEBLOG'], yrmn))
         for logfile in logfiles:
            try:
               cod = open(logfile, 'r')
            except Exception as e:
               self.pglog("{}: {}".format(logfile, str(e)), self.LOGWRN)
               continue
            self.pglog("Gathering custom OPeNDAP usage info from {} at {}".format(logfile, self.current_datetime()), self.LOGWRN)
            pdate = ''
            records = {}
            while True:
               line = cod.readline()
               if not line: break
               cntall += 1
               if cntall%20000 == 0:
                  s = 's' if cntadd > 1 else ''
                  self.pglog("{}/{} COD log entries processed/records added".format(cntall, cntadd), self.WARNLG)
               ms = re.search(r'GET /opendap/(\w{10})\.dods.*\s200\s+(\d+).{6}([^"]+)', line)
               if not ms: continue
               aid = ms.group(1)
               size = int(ms.group(2))
               engine = ms.group(3)
               if not (aid in self.USERS or self.cache_users(aid)): continue
               ms = re.match(r'^([\d\.]+).+\[(\d+)/(\w+)/(\d+):([\d:]+)', line)
               if not ms: continue
               ip = ms.group(1)
               ctime = ms.group(5)
               cdate = "{}-{:02}-{:02}".format(ms.group(4), self.get_month(ms.group(3)), int(ms.group(2)))
               if pdate != cdate:
                  if records:
                     cntadd += self.add_usage_records(records, cdate)
                     records = {}            
                  pdate = cdate
               if self.datelimit and cdate < self.datelimit: continue
               if aid in records:
                  records[aid]['size'] += size
                  records[aid]['count'] += 1
                  self.USERS[aid]['etime'] = ctime
               else:
                  records[aid] = {}
                  records[aid]['ip'] = ip
                  records[aid]['count'] = 1
                  records[aid]['email'] = self.USERS[aid]['email']
                  records[aid]['dsid'] = self.USERS[aid]['dsid']
                  records[aid]['size'] = size
                  records[aid]['engine'] = engine
                  self.USERS[aid]['etime'] = ctime
                  self.USERS[aid]['btime'] = ctime
            cod.close()
            if records: cntadd += self.add_usage_records(records, cdate)
      s = 's' if cntadd > 1 else ''
      self.pglog("{} COD usage records added for {} entries at {}".format(cntadd, cntall, self.current_datetime()), self.LOGWRN)

   # add usage to codusage table
   def add_usage_records(self, records, date):
      ms = re.match(r'(\d+)-(\d+)-', date)
      if not ms: return 0
      year = ms.group(1)
      quarter = 1 + int((int(ms.group(2)) - 1) / 3)
      cnt = 0
      for aid in records:
         if self.pgget(self.USAGE['PGTBL'], '', "aid = '{}' AND date = '{}'".format(aid, date), self.LGEREX): continue
         record = records[aid]
         if record['email'] == '-':
            wurec = self.get_wuser_record(record['ip'], date)
            if not wurec: continue
            record['org_type'] = wurec['org_type']
            record['country'] = wurec['country']
            record['region'] = wurec['region']
            record['email'] = 'unknown@' + wurec['hostname']
         else:
            wuid = self.check_wuser_wuid(record['email'], date)
            if not wuid: continue
            pgrec = self.pgget("wuser",  "org_type, country, region", "wuid = {}".format(wuid), self.LGWNEX)
            if not pgrec: continue
            record['org_type'] = pgrec['org_type']
            record['country'] = pgrec['country']
            record['region'] = pgrec['region']
         record['date'] = date
         record['time'] = self.USERS[aid]['btime']
         record['quarter'] = quarter
         if self.add_to_allusage(record, year):
            record['aid'] = aid
            record['period'] = self.access_period(self.USERS[aid]['etime'], record['time'])
            cnt += self.pgadd(self.USAGE['PGTBL'], record, self.LOGWRN)
      return cnt

   # add usage to allusage tables
   def add_to_allusage(self, pgrec, year):
      record = {'method' : 'COD', 'source' : 'C'}
      for fld in pgrec:
         ms = re.match(r'^(engine|count)$', fld)
         if ms: continue
         record[fld] = pgrec[fld]
      return self.add_yearly_allusage(year, record)   # change 1 to 0 to stop checking

   # cashe user info for reuse
   def cache_users(self, aid):
      pgrec = self.pgget("metautil.custom_dap_history", "*", "ID = '{}'".format(aid), self.LGEREX)
      if pgrec:
         ms = re.search(r'dsnum=(\d+\.\d|[a-z]\d{6});', pgrec['rinfo'])
         if ms:
            dsid = self.format_dataset_id(ms.group(1))
            self.USERS[aid]= {'dsid' : dsid, 'email' : pgrec['duser']}
            return 1
      return 0

   # get period
   def access_period(self, etime, btime):
      period = 86400
      ms = re.search(r'(\d+):(\d+):(\d+)', etime)
      if ms:
         period = int(ms.group(1))*3600+int(ms.group(2))*60+int(ms.group(3))
      ms = re.search(r'(\d+):(\d+):(\d+)', btime)
      if ms:
         period -= int(ms.group(1))*3600+int(ms.group(2))*60+int(ms.group(3))
      return period

# main function to excecute this script
def main():
   object = FillCODUsage()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
