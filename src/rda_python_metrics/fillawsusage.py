#!/usr/bin/env python3
###############################################################################
#     Title : fillawsusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/11/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-16 converted to class FillAWSUsage
#   Purpose : python program to retrieve info from AWS logs 
#             and fill table wusages in PgSQL database dssdb.
#    Github : https://github.com/NCAR/rda-pythn-metrics.git
###############################################################################
import sys
import re
import glob
from os import path as op
from rda_python_common.pg_file import PgFile
from .pg_ipinfo import PgIPInfo

class FillAWSUsage(PgIPInfo, PgFile):

   def __init__(self):
      super().__init()
      self.USAGE = {
         'PGTBL'  : "awsusage",
         'AWSDIR' : self.PGLOG["TRANSFER"] + "/AWSera5log",
         'AWSLOG' : "{}/{}-00-00-00-*",
         'PFMT'   : "YYYY/MM/DD"
      }
      self.DSIDS = {'nsf-ncar-era5' : 'd633000'}
      self.option = self.cmdstr = None
      self.params = []  # array of input values

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
      if not (self.option and self.params): self.show_usage('fillawsusage')
      self.dssdb_dbname()
      self.cmdstr = "fillawsusage {}".format(' '.join(argv))
      self.cmdlog(self.cmdstr)

   # function to start actions
   def start_actions(self):
      self.change_local_directory(self.USAGE['AWSDIR'])
      filenames = self.get_log_file_names()
      if filenames:
         self.fill_aws_usages(filenames)
      else:
        self.pglog("No log file found for given command: " + self.cmdstr, self.LOGWRN)
      self.pglog(None, self.LOGWRN)

   # get the log file dates 
   def get_log_file_names(self):
      filenames = {}
      if self.option == 'd':
         for dt in self.params:
            pdate = self.format_date(dt)
            pd = self.format_date(pdate, self.USAGE['PFMT'])
            fname = self.USAGE['AWSLOG'].format(pd, pdate)
            fnames = glob.glob(fname)
            if fnames: filenames[pdate] = sorted(fnames)
      else:
         if self.option == 'N':
            edate = self.curdate()
            pdate = self.adddate(edate, 0, 0, -int(self.params[0]))
         else:
            pdate = self.format_date(self.params[0])
            if len(self.params) > 1:
               edate = self.adddate(self.format_date(self.params[1]), 0, 0, 1)
            else:
               edate = self.curdate()
         while pdate < edate:
            pd = self.format_date(pdate, self.USAGE['PFMT'])
            fname = self.USAGE['AWSLOG'].format(pd, pdate)
            fnames = glob.glob(fname)
            if fnames: filenames[pdate] = sorted(fnames)
            pdate = self.adddate(pdate, 0, 0, 1)
      return filenames

   # Fill AWS usages into table dssdb.awsusage of DSS PgSQL database from aws access logs
   def fill_aws_usages(self, filenames):
      year = cntall = addall = 0
      for pdate in filenames:
         fnames = filenames[pdate]
         fcnt = len(fnames)
         self.pglog("{}: Gathering AWS usage info from {} log files at {}".format(pdate, fcnt, self.current_datetime()), self.LOGWRN)
         records = {}
         cntadd = entcnt = 0
         for logfile in fnames:
            aws = self.open_local_file(logfile)
            if not aws: continue
            while True:
               line = aws.readline()
               if not line: break
               entcnt += 1
               if entcnt%20000 == 0:
                  dcnt = len(records)
                  self.pglog("{}: {}/{} AWS log entries processed/records to add".format(pdate, entcnt, dcnt), self.WARNLG)
               ms = re.match(r'^\w+ ([\w-]+) \[(\S+).*\] ([\d\.]+) .+ REST\.GET\.OBJECT \S+ "GET.+" \d+ - (\d+) \d+ .* ".+" "(.+)" ', line)
               if not ms: continue
               values = list(ms.groups())
               if values[0] not in self.DSIDS: continue
               dsid = self.DSIDS[values[0]]
               size = int(values[3])
               ip = values[2]
               engine = values[4]
               moff = engine.find('/')
               if moff > 0:
                  if moff > 20: moff = 20
                  method = engine[0:moff].upper()
               else:
                  method = "AWS"
               key = "{}:{}:{}".format(ip, dsid, method)
               if key in records:
                  records[key]['size'] += size
                  records[key]['fcount'] += 1
               else:
                  (year, quarter, date, time) = self.get_record_date_time(values[1])
                  iprec =  self.get_missing_ipinfo(ip)
                  if not iprec: continue
                  records[key] = {'ip' : ip, 'dsid' : dsid, 'date' : date, 'time' : time, 'quarter' : quarter,
                                  'size' : size, 'fcount' : 1, 'method' : method, 'engine' : engine,
                                  'org_type' : iprec['org_type'], 'country' : iprec['country'],
                                  'region' : iprec['region'], 'email' : iprec['email']}
            aws.close()
         if records: cntadd = self.add_usage_records(records, year)
         self.pglog("{}: {} AWS usage records added for {} entries at {}".format(pdate, cntadd, entcnt, self.current_datetime()), self.LOGWRN)
         cntall += entcnt
         if cntadd:
            addall += cntadd
            if addall > cntadd:
               self.pglog("{} AWS usage records added for {} entries at {}".format(addall, cntall, self.current_datetime()), self.LOGWRN)

   # get date and time from record
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

   # add usage records for year
   def add_usage_records(self, records, year):
      cnt = 0
      for key in records:
         record = records[key]
         cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(record['date'], record['time'], record['ip'])
         if self.pgget(self.USAGE['PGTBL'], '', cond, self.LGEREX): continue
         if self.add_to_allusage(year, record):
            cnt += self.pgadd(self.USAGE['PGTBL'], record, self.LOGWRN)
      return cnt

   # add record to allusage tables
   def add_to_allusage(self, year, pgrec):
      record = {'source' : 'A'}
      flds = ['ip', 'dsid', 'date', 'time', 'quarter', 'size', 'method',
              'org_type', 'country', 'region', 'email']
      for fld in flds:
         record[fld] = pgrec[fld]
      return self.add_yearly_allusage(year, record)

# main function to excecute this script
def main():
   object = FillAWSUsage()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
