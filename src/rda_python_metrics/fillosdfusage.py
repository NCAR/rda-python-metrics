#!/usr/bin/env python3
###############################################################################
#
#     Title : fillosdfusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2025-04-01
#             2025-12-17 convert to class FillOSDFUsage
#   Purpose : python program to retrieve info from weekly OSDF logs 
#             and fill table wusages in PgSQL database dssdb.
#    Github : https://github.com/NCAR/rda-pythn-metrics.git
###############################################################################
import sys
import re
from rda_python_common.pg_file import PgFile
from rda_python_common.pg_split import PgSplit
from .pg_ipinfo import PgIPInfo

class FillOSDFUsage(PgIPInfo, PgFile, PgSplit):

   def __init__(self):
      super().__init__()
      self.USAGE = {
         'OSDFTBL'  : "osdfusage",
         'OSDFDIR' : self.PGLOG["GDEXWORK"] + "/zji/osdflogs/",
         'OSDFGET' : 'wget -m -nH -np -nd https://pelicanplatform.org/pelican-access-logs/ncar-access-log/',
         'OSDFLOG' : "{}-cache.log",   # YYYY-MM-DD-cache.log
      }
      self.params = []  # array of input values
      self.datelimits = [None, None]
      self.logfiles = []
      self.option = self.cmdstr = None

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
      if not (self.option and self.params): self.show_usage('fillosdfusage')
      self.cmdstr = "fillosdfusage {}".format(' '.join(argv))
      self.cmdlog(self.cmdstr)

   # function to start actions
   def start_actions(self):
      self.dssdb_dbname()
      self.change_local_directory(self.USAGE['OSDFDIR'])
      self.get_log_file_names()
      if self.logfiles:
         self.fill_osdf_usages()
      else:
         self.pglog("No log file found for given command: " + self.cmdstr, self.LOGWRN)
      self.pglog(None, self.LOGWRN)

   # get the log file dates 
   def get_log_file_names(self):
      if self.option == 'd':
         for pdate in self.params:
            self.logfiles.append(self.USAGE['OSDFLOG'].format(pdate))
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
            self.logfiles.append(self.USAGE['OSDFLOG'].format(pdate))
            pdate = self.adddate(pdate, 0, 0, 1)

   # Fill OSDF usages into table dssdb.osdfusage of DSS PgSQL database from osdf access logs
   def fill_osdf_usages(self):
      year = cntall = addall = 0
      for logfile in self.logfiles:
         linfo = self.check_local_file(logfile)
         if not linfo:
            xzfile = logfile + '.xz'
            self.pgsystem(self.USAGE['OSDFGET'] + xzfile, 5, self.LOGWRN)
            linfo = self.check_local_file(xzfile)
            if not linfo:
               self.pglog("{}: Not exists for Gathering OSDF usage".format(xzfile), self.LOGWRN)
               continue
            self.compress_local_file(xzfile)
            linfo = self.check_local_file(logfile)
            if not linfo:
               self.pglog("{}: Error unxz OSDF usage".format(xzfile), self.LGEREX)
         self.pglog("{}: Gathering OSDF usage at {}".format(logfile, self.current_datetime()), self.LOGWRN)
         osdf = self.open_local_file(logfile)
         if not osdf: continue
         records = {}
         cntadd = entcnt = 0
         while True:
            line = osdf.readline()
            if not line: break
            entcnt += 1
            if entcnt%20000 == 0:
               dcnt = len(records)
               self.pglog("{}: {}/{} OSDF log entries processed/records added".format(logfile, entcnt, dcnt), self.WARNLG)
            ms = re.match(r'^\[(\S+)\] \[Objectname:\/ncar\/rda\/([a-z]\d{6})\/\S+\].* \[Site:(\S+)\].* \[Host:(\S+)\].* \[AppInfo:(\S+)\].* \[Read:(\d+)\]', line)
            if not ms: continue
            dt = ms.group(1)
            dsid = ms.group(2)
            site = ms.group(3)
            ip = ms.group(4)
            if ip == 'N/A': ip = self.GIP
            engine = ms.group(5)
            size = int(ms.group(6))
            if re.match(r'^N/A', engine, re.I):
               method = "OSDF"
            else:
               moff = engine.find('/')
               if moff > 0:
                  if moff > 20: moff = 20
                  method = engine[0:moff].upper()
               else:
                  method = "OSDF"
            key = "{}:{}:{}".format(ip, dsid, method)
            if key in records:
               records[key]['size'] += size
               records[key]['fcount'] += 1
            else:
               (year, quarter, date, time) = self.get_record_date_time(dt)
               iprec =  self.get_missing_ipinfo(ip)
               if not iprec: continue
               records[key] = {'ip' : iprec['ip'], 'dsid' : dsid, 'date' : date, 'time' : time, 'quarter' : quarter,
                               'size' : size, 'fcount' : 1, 'method' : method, 'engine' : engine,
                               'org_type' : iprec['org_type'], 'country' : iprec['country'],
                               'region' : iprec['region'], 'email' : iprec['email'], 'site' : site}
         osdf.close()
         if records: cntadd = self.add_usage_records(records, year)
         self.pglog("{}: {} OSDF usage records added for {} entries at {}".format(logfile, cntadd, entcnt, self.current_datetime()), self.LOGWRN)
         cntall += entcnt
         if cntadd:
            addall += cntadd
            if addall > cntadd:
               self.pglog("{} OSDF usage records added for {} entries at {}".format(addall, cntall, self.current_datetime()), self.LOGWRN)

   # get date and time from log entry
   def get_record_date_time(self, ctime):
      ms = re.search(r'^(\d+)-(\d+)-(\d+)T([\d:]+)\.', ctime)
      if ms:
         y = ms.group(1)
         m = int(ms.group(2))
         d = int(ms.group(3))
         t = ms.group(4)
         q = 1 + int((m-1)/3)
         return (y, q, "{}-{:02}-{:02}".format(y, m, d), t)
      else:
         self.pglog(ctime + ": Invalid date/time format", self.LGEREX)

   # add usage to table osdusage
   def add_usage_records(self, records, year):
      cnt = 0
      for key in records:
         record = records[key]
         cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(record['date'], record['time'], record['ip'])
         if self.pgget(self.USAGE['OSDFTBL'], '', cond, self.LGEREX): continue
         if self.add_to_allusage(year, record):
            cnt += self.pgadd(self.USAGE['OSDFTBL'], record, self.LOGWRN)
      return cnt

   # add record to table allusage
   def add_to_allusage(self, year, pgrec):
      record = {'source' : 'P'}
      flds = ['ip', 'dsid', 'date', 'time', 'quarter', 'size', 'method',
              'org_type', 'country', 'region', 'email']
      for fld in flds:
         record[fld] = pgrec[fld]
      return self.add_yearly_allusage(year, record)

# main function to excecute this script
def main():
   object = FillOSDFUsage()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
