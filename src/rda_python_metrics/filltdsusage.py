#!/usr/bin/env python3
#
###############################################################################
#
#     Title : filltdsusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/11/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to retrieve info from TDS logs 
#             and fill table tdsusage in PostgreSQL database dssdb.
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

# the define options for gathering TDS data usage, one at a time
MONTH = 0x02  # fet TDS data usages for given months
YEARS = 0x04  # get TDS data usages for given years
NDAYS = 0x08  # get TDS data usages in recent number of days 
MASKS = (MONTH|YEARS|NDAYS)

USAGE = {
   'OPTION' : 0,
   'PGTBL'  : "tdsusage",
   'TDSLOG' : "/data/logs/nginx/{}.access.log",
   'CDATE' : PgUtil.curdate()
}

#
# main function to run this program
#
def main():

   params = []  # array of input values
   argv = sys.argv[1:]
   datelimit = ''
   fixrec = False
   
   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
      elif arg == "-f":
         fixrec = True
      elif re.match(r'^-[mNy]$', arg) and USAGE['OPTION'] == 0:
         if arg == "-m":
            USAGE['OPTION'] = MONTH
         elif arg == "-y":
            USAGE['OPTION'] = YEARS
         elif arg == "-N":
            USAGE['OPTION'] = NDAYS
      elif re.match(r'^-', arg):
         PgLOG.pglog(arg + ": Invalid Option", PgLOG.LGWNEX)
      elif USAGE['OPTION']&MASKS:
         params.append(arg)
      else:
         PgLOG.pglog(arg + ": Invalid Parameter", PgLOG.LGWNEX)
   
   if not (USAGE['OPTION'] and params): PgLOG.show_usage('filltdsusage')
   PgDBI.dssdb_dbname()
   PgLOG.cmdlog("filltdsusage {}".format(' '.join(argv)))

   if fixrec:
      fix_tds_usages(USAGE['OPTION'], params)
   else:
      if USAGE['OPTION']&NDAYS:
         curdate = USAGE['CDATE']
         datelimit = PgUtil.adddate(curdate, 0, 0, -int(params[0]))  
         USAGE['OPTION'] = MONTH
         params = []
         
         while curdate >= datelimit:
            tms = curdate.split('-')
            params.append("{}-{}".format(tms[0], tms[1]))
            curdate = PgUtil.adddate(curdate, 0, 0, -int(tms[2]))
   
      fill_tds_usages(USAGE['OPTION'], params, datelimit)

   PgLOG.pglog(None, PgLOG.LOGWRN|PgLOG.SNDEML)  # send email out if any

   sys.exit(0)

#
# Fill TDS usages into table dssdb.tdsusage from tds access logs
#
def fill_tds_usages(option, inputs, datelimit):

   cntall = cntadd = 0

   for input in inputs:
      # get log file names
      if option&MONTH:
         tms = input.split('-')
         yrmn = "{}-{:02}".format(tms[0], int(tms[1]))
      else:
         yrmn = input

      logfiles = glob.glob(USAGE['TDSLOG'].format(yrmn + '*'))
      if not logfiles: PgLOG.pglog("{}: No file found to gather TDS usage".format(yrmn), PgLOG.LOGWRN)
      for logfile in logfiles:
         if not op.isfile(logfile):
            PgLOG.pglog("{}: Not exists to gather TDS usage".format(logfile), PgLOG.LOGWRN)
            continue
         fdate = None
         ms = re.search(r'(\d+-\d+-\d+).access.log$', logfile)
         if ms:
            fdate = ms.group(1)
            if fdate >= USAGE['CDATE']: continue
            if datelimit and fdate < datelimit: continue
         PgLOG.pglog("Gathering usage info from {} at {}".format(logfile, PgLOG.current_datetime()), PgLOG.LOGWRN)
         tds = PgFile.open_local_file(logfile)
         if not tds: continue
         ptime = ''
         records = {}
         entcnt = 0
         while True:
            line = tds.readline()
            if not line: break
            entcnt += 1
            if entcnt%20000 == 0:
               cnt = len(records)
               PgLOG.pglog("{}/{} TDS log entries processed/records to add".format(entcnt, cnt), PgLOG.WARNLG)

            ms = re.search(r'(/thredds/catalog|\sGooglebot/)', line)
            if ms: continue
            ms = re.search(r'/thredds/\S+\.(png|jpg|gif|css|htm)', line)
            if ms: continue
            ms = re.match(r'^([\d\.]+)\s.*\s(-|\S+@\S+)\s+\[(\S+).*/thredds/(\w+)(/|/grid/)(aggregations|files).*/(ds\d\d\d.\d|[a-z]\d{6})/.*\s200\s+(\d+)(.*)$', line)
            if not ms: continue
            ip = ms.group(1)
            email = ms.group(2)
            (date, time) = get_record_date_time(ms.group(3))
            method = ms.group(4)
            etype = ms.group(6)[0].upper()
            dsid = PgUtil.format_dataset_id(ms.group(7))
            size = int(ms.group(8))
            ebuf = ms.group(9)
            ms = re.search(r' "(\w+.*\S+)" ', ebuf)
            engine = ms.group(1) if ms else 'Unknown'
            key = "{}:{}:{}:{}".format(ip, dsid, method, etype)

            if key in records:
               records[key]['size'] += size
               records[key]['fcount'] += 1
            else:
               records[key] = {'ip' : ip, 'email' : email, 'dsid' : dsid, 'time' : time, 'size' : size,
                              'fcount' : 1, 'method' : method, 'etype' : etype, 'engine' : engine}
         tds.close()
         if records: cntadd += add_usage_records(records, fdate)
         cntall += entcnt

   PgLOG.pglog("{} TDS usage records added for {} entries at {}".format(cntadd, cntall, PgLOG.current_datetime()), PgLOG.LOGWRN)


def get_record_date_time(ctime):
   
   ms = re.search(r'^(\d+)/(\w+)/(\d+):(\d+:\d+:\d+)$', ctime)
   if ms:
      d = int(ms.group(1))
      m = PgUtil.get_month(ms.group(2))
      y = ms.group(3)
      t = ms.group(4)
      return ("{}-{:02}-{:02}".format(y, m, d), t)
   else:
      PgLOG.pglog("time: Invalid date format", PgLOG.LGEREX)

def add_usage_records(records, date):

   quarter = cnt = 0
   year = None
   ms = re.search(r'(\d+)-(\d+)-', date)
   if ms:
      year = ms.group(1)
      quarter = 1 + int((int(ms.group(2)) - 1)/3)
   for key in records:
      record = records[key]
      cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(date, record['time'], record['ip'])
      if PgDBI.pgget(USAGE['PGTBL'], '', cond, PgLOG.LGEREX): continue
      if record['email'] == '-':
         record['org_type'] = record['country'] = '-'
         ipinfo = PgIPInfo.set_ipinfo(record['ip'])
         if ipinfo:
            record['org_type'] = ipinfo['org_type']
            record['country'] = ipinfo['country']
            record['email'] = 'unknown@' + ipinfo['hostname']
      else:
         wuid = PgDBI.check_wuser_wuid(record['email'], date)
         if not wuid: continue
         pgrec = PgDBI.pgget("wuser",  "org_type, country", "wuid = {}".format(wuid), PgLOG.LGWNEX)
         if not pgrec: continue
         record['org_type'] = pgrec['org_type']
         record['country'] = pgrec['country']

      record['quarter'] = quarter
      record['date'] = date

      if add_to_allusage(year, record):
         cnt += PgDBI.pgadd(USAGE['PGTBL'], record, PgLOG.LOGWRN)

   PgLOG.pglog("{}: {} TDS usage records added at {}".format(date, cnt, PgLOG.current_datetime()), PgLOG.LOGWRN)

   return cnt


def add_to_allusage(year, pgrec):

   record = {'method' : 'TDS', 'source' : 'T'}

   for fld in pgrec:
      if re.match(r'^(engine|method|etype|fcount)$', fld): continue
      record[fld] = pgrec[fld]

   return PgDBI.add_yearly_allusage(year, record)

#
# Fix TDS usages in table dssdb.tdsusage by combine tds accesses with same ip,dsid,method&etype
#
def fix_tds_usages(option, inputs):

   cntall = cntfix = 0

   for input in inputs:
      if option&NDAYS:
         edate = USAGE['CDATE']
         date = PgUtil.adddate(edate, 0, 0, -int(input))  
      elif option&MONTH:
         tms = input.split('-')
         date = "{}-{:02}-01".format(tms[0], int(tms[1]))
         edate = PgUtil.enddate(date, 0, 'M')
      else:
         date = input + "-01-01"
         edate = input + "-12-31"

      while date <= edate:
         cond = "date = '{}' and fcount = 0 order by time".format(date)
         pgrecs = PgDBI.pgmget(USAGE['PGTBL'], '*', cond, PgLOG.LGEREX)
         cnt = len(pgrecs['ip']) if pgrecs else 0
         records = {}
         for i in range(cnt):
            record = PgUtil.onerecord(pgrecs, i)
            key = "{}:{}:{}:{}".format(record['ip'], record['dsid'], record['method'], record['etype'])
            if key in records:
               records[key]['size'] += record['size']
               records[key]['fcount'] += 1
            else:
               record['fcount'] = 1
               records[key] = record

         if records: cntfix += fix_usage_records(records, date)
         cntall += cnt
         date = PgUtil.adddate(date, 0, 0, 1)

   PgLOG.pglog("{} TDS usage records combined into {} at {}".format(cntall, cntfix, PgLOG.current_datetime()), PgLOG.LOGWRN)

def fix_usage_records(records, date):

   cnt = 0
   ms = re.match(r'^(\d+)-', date)
   year = ms.group(1)
   tname = 'allusage_' + year
   dcnt = PgDBI.pgdel(tname , "date = '{}' AND method = 'TDS'".format(date), PgLOG.LOGWRN)
   PgLOG.pglog("{} TDS usage records deleted for {} from {}".format(dcnt, date, tname), PgLOG.LOGWRN)
   for key in records:
      record = records[key]
      cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(date, record['time'], record['ip'])
      if add_to_allusage(year, record):
         cnt += PgDBI.pgupdt(USAGE['PGTBL'], record, cond, PgLOG.LOGWRN)

   if cnt:
      PgLOG.pglog("{} TDS usage records updated for {} in {}".format(cnt, date, USAGE['PGTBL']), PgLOG.LOGWRN)
      dcnt = PgDBI.pgdel(USAGE['PGTBL'], "date = '{}' and fcount = 0".format(date), PgLOG.LOGWRN) 
      PgLOG.pglog("{} TDS usage records deleted for {} from {}".format(dcnt, date, USAGE['PGTBL']), PgLOG.LOGWRN)

   return cnt

#
# call main() to start program
#
if __name__ == "__main__": main()
