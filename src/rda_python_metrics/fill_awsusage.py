#!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillawsusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/11/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to retrieve info from AWS logs 
#             and fill table wusages in PgSQL database dssdb.
# 
#    Github : https://github.com/NCAR/rda-pythn-metrics.git
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

USAGE = {
   'PGTBL'  : "awsusage",
   'AWSDIR' : PgLOG.PGLOG["TRANSFER"] + "/AWSera5log",
   'AWSLOG' : "{}/{}-00-00-00-*",
   'PFMT'   : "YYYY/MM/DD"
}

DSIDS = {'nsf-ncar-era5' : 'd633000'}

#
# main function to run this program
#
def main():

   params = []  # array of input values
   argv = sys.argv[1:]
   option = None

   for arg in argv:
      ms = re.match(r'^-(b|d|p|N)$', arg)
      if ms:
         opt = ms.group(1)
         if opt == 'b':
            PgLOG.PGLOG['BCKGRND'] = 1
         elif option:
            PgLOG.pglog("{}: Option -{} is present already".format(arg, option), PgLOG.LGWNEX)
         else:
            option = opt
      elif re.match(r'^-', arg):
         PgLOG.pglog(arg + ": Invalid Option", PgLOG.LGWNEX)
      elif option:
         params.append(arg)
      else:
         PgLOG.pglog(arg + ": Invalid Parameter", PgLOG.LGWNEX)
   
   if not (option and params): PgLOG.show_usage('fillawsusage')

   PgDBI.dssdb_dbname()
   cmdstr = "fillawsusage {}".format(' '.join(argv))
   PgLOG.cmdlog(cmdstr)
   PgFile.change_local_directory(USAGE['AWSDIR'])
   filenames = get_log_file_names(option, params)
   if filenames:
      fill_aws_usages(filenames)
   else:
      PgLOG.pglog("No log file found for given command: " + cmdstr, PgLOG.LOGWRN)

   PgLOG.pglog(None, PgLOG.LOGWRN)
   sys.exit(0)

#
# get the log file dates 
#
def get_log_file_names(option, params):

   filenames = {}
   if option == 'd':
      for dt in params:
         pdate = PgUtil.format_date(dt)
         pd = PgUtil.format_date(pdate, USAGE['PFMT'])
         fname = USAGE['AWSLOG'].format(pd, pdate)
         fnames = glob.glob(fname)
         if fnames: filenames[pdate] = sorted(fnames)
   else:
      if option == 'N':
         edate = PgUtil.curdate()
         pdate = PgUtil.adddate(edate, 0, 0, -int(params[0]))
      else:
         pdate = PgUtil.format_date(params[0])
         if len(params) > 1:
            edate = PgUtil.adddate(PgUtil.format_date(params[1]), 0, 0, 1)
         else:
            edate = PgUtil.curdate()
      while pdate < edate:
         pd = PgUtil.format_date(pdate, USAGE['PFMT'])
         fname = USAGE['AWSLOG'].format(pd, pdate)
         fnames = glob.glob(fname)
         if fnames: filenames[pdate] = sorted(fnames)
         pdate = PgUtil.adddate(pdate, 0, 0, 1)

   return filenames

#
# Fill AWS usages into table dssdb.awsusage of DSS PgSQL database from aws access logs
#
def fill_aws_usages(filenames):

   year = cntall = addall = 0
   for pdate in filenames:
      fnames = filenames[pdate]
      fcnt = len(fnames)
      PgLOG.pglog("{}: Gathering AWS usage info from {} log files at {}".format(pdate, fcnt, PgLOG.current_datetime()), PgLOG.LOGWRN)
      records = {}
      cntadd = entcnt = 0
      for logfile in fnames:
         if not op.isfile(logfile):
            PgLOG.pglog("{}: Not exists for Gathering AWS usage".format(logfile), PgLOG.LOGWRN)
            continue
         aws = PgFile.open_local_file(logfile)
         if not aws: continue
         while True:
            line = aws.readline()
            if not line: break
            entcnt += 1
            if entcnt%20000 == 0:
               dcnt = len(records)
               PgLOG.pglog("{}: {}/{} AWS log entries processed/records to add".format(pdate, entcnt, dcnt), PgLOG.WARNLG)
   
            ms = re.match(r'^\w+ ([\w-]+) \[(\S+).*\] ([\d\.]+) .+ REST\.GET\.OBJECT \S+ "GET.+" \d+ - (\d+) \d+ .* ".+" "(.+)" ', line)
            if not ms: continue
            values = list(ms.groups())
            if values[0] not in DSIDS: continue
            dsid = DSIDS[values[0]]
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
               (year, quarter, date, time) = get_record_date_time(values[1])
               iprec =  PgIPInfo.get_missing_ipinfo(ip)
               if not iprec: continue
               records[key] = {'ip' : ip, 'dsid' : dsid, 'date' : date, 'time' : time, 'quarter' : quarter,
                               'size' : size, 'fcount' : 1, 'method' : method, 'engine' : engine,
                               'org_type' : iprec['org_type'], 'country' : iprec['country'],
                               'region' : iprec['region'], 'email' : iprec['email']}
         aws.close()
      if records: cntadd = add_usage_records(records, year)
      PgLOG.pglog("{}: {} AWS usage records added for {} entries at {}".format(pdate, cntadd, entcnt, PgLOG.current_datetime()), PgLOG.LOGWRN)
      cntall += entcnt
      if cntadd:
         addall += cntadd
         if addall > cntadd:
            PgLOG.pglog("{} AWS usage records added for {} entries at {}".format(addall, cntall, PgLOG.current_datetime()), PgLOG.LOGWRN)

def get_record_date_time(ctime):
   
   ms = re.search(r'^(\d+)/(\w+)/(\d+):(\d+:\d+:\d+)$', ctime)
   if ms:
      d = int(ms.group(1))
      m = PgUtil.get_month(ms.group(2))
      y = ms.group(3)
      t = ms.group(4)
      q = 1 + int((m-1)/3)
      return (y, q, "{}-{:02}-{:02}".format(y, m, d), t)
   else:
      PgLOG.pglog(ctime + ": Invalid date/time format", PgLOG.LGEREX)

def add_usage_records(records, year):

   cnt = 0
   for key in records:
      record = records[key]
      cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(record['date'], record['time'], record['ip'])
      if PgDBI.pgget(USAGE['PGTBL'], '', cond, PgLOG.LGEREX): continue
      if add_to_allusage(year, record):
         cnt += PgDBI.pgadd(USAGE['PGTBL'], record, PgLOG.LOGWRN)

   return cnt


def add_to_allusage(year, pgrec):

   record = {'source' : 'A'}
   flds = ['ip', 'dsid', 'date', 'time', 'quarter', 'size', 'method',
           'org_type', 'country', 'region', 'email']

   for fld in flds:
      record[fld] = pgrec[fld]

   return PgDBI.add_yearly_allusage(year, record)

#
# call main() to start program
#
if __name__ == "__main__": main()
