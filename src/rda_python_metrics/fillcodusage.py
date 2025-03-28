#!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillcodusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/11/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to retrieve info from web logs 
#             and fill table codusage in PgSQL database dssdb.
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

# the define options for gathering COD data usage, one at a time
MONTH = 0x02  # fet COD data usages for given months
YEARS = 0x04  # get COD data usages for given years
NDAYS = 0x08  # get COD data usages in recent number of days 
FILES = 0x10  # get given file names
GTALL = 0x20  # get all data files of read
MASKS = (MONTH|YEARS|NDAYS|FILES)

USAGE = {
   'OPTION' : 0,
   'PGTBL'  : "codusage",
   'WEBLOG' : "/var/log/httpd",
}

USERS = {}  # cache user info for aid

#
# main function to run this program
#
def main():

   params = []  # array of input values
   argv = sys.argv[1:]
   datelimit = ''

   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
      elif re.match(r'^-[afmNy]$', arg) and USAGE['OPTION'] == 0:
         if arg == "-a":
            USAGE['OPTION'] = GTALL
            params = ['']
         elif arg == "-f":
            USAGE['OPTION'] = FILES
         elif arg == "-m":
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
   
   if not (USAGE['OPTION'] and params): PgLOG.show_usage('fillcodusage')

   PgDBI.dssdb_dbname()
   PgLOG.cmdlog("fillcodusage {}".format(' '.join(argv)))
   
   if USAGE['OPTION']&NDAYS:
      curdate = PgUtil.curdate()
      datelimit = PgUtil.adddate(curdate, 0, 0, -int(params[0]))
   
      USAGE['OPTION'] = MONTH
      params = []
      
      while curdate >= datelimit:
         (year, month, day) = curdate.split('-')
         params.append("{}-{}".format(year, month))
         curdate = PgUtil.adddate(curdate, 0, 0, -int(day))
   
   fill_cod_usages(USAGE['OPTION'], params, datelimit)
   
   PgLOG.pglog(None, PgLOG.LOGWRN|PgLOG.SNDEML)  # send email out if any
   
   sys.exit(0)

#
# Fill COD usages into table dssdb.codusage of DSS PgSQL database from cod access logs
#
def fill_cod_usages(option, inputs, datelimit):

   cntall = cntadd = 0

   for input in inputs:
      # get log file names
      if option&FILES:
         logfiles = [input]
      elif option&MONTH:
         tms = input.split('-')
         yrmn = "{}{:02}".format(tms[0], int(tms[1]))
         logfiles = ["{}/{}/access_log".format(USAGE['WEBLOG'], yrmn)]
      else: # GTALL | YEARS
         yrmn = input + "*"
         logfiles = glob.glob("{}/{}/access_log".format(USAGE['WEBLOG'], yrmn))
   
      for logfile in logfiles:
         if not op.isfile(logfile):
            PgLOG.pglog("{}: Not exists for Gathering custom OPeNDAP usage".format(logfile), PgLOG.LOGWRN)
            continue
         PgLOG.pglog("Gathering custom OPeNDAP usage info from {} at {}".format(logfile, PgLOG.current_datetime()), PgLOG.LOGWRN)
         cod = PgFile.open_local_file(logfile)
         if not cod: continue

         pdate = ''
         records = {}
         while True:
            line = cod.readline()
            if not line: break
            cntall += 1
            if cntall%20000 == 0:
               s = 's' if cntadd > 1 else ''
               PgLOG.pglog("{}/{} COD log entries processed/records added".format(cntall, cntadd), PgLOG.WARNLG)
         
            ms = re.search(r'GET /opendap/(\w{10})\.dods.*\s200\s+(\d+).{6}([^"]+)', line)
            if not ms: continue
            aid = ms.group(1)
            size = int(ms.group(2))
            engine = ms.group(3)
            if not (aid in USERS or cache_users(aid)): continue
            ms = re.match(r'^([\d\.]+).+\[(\d+)/(\w+)/(\d+):([\d:]+)', line)
            if not ms: continue
            ip = ms.group(1)
            ctime = ms.group(5)
            cdate = "{}-{:02}-{:02}".format(ms.group(4), PgUtil.get_month(ms.group(3)), int(ms.group(2)))
            if pdate != cdate:
               if records:
                  cntadd += add_usage_records(records, cdate)
                  records = {}            
               pdate = cdate
         
            if datelimit and cdate < datelimit: continue

            if aid in records:
               records[aid]['size'] += size
               records[aid]['count'] += 1
               USERS[aid]['etime'] = ctime
            else:
               records[aid] = {}
               records[aid]['ip'] = ip
               records[aid]['count'] = 1
               records[aid]['email'] = USERS[aid]['email']
               records[aid]['dsid'] = USERS[aid]['dsid']
               records[aid]['size'] = size
               records[aid]['engine'] = engine
               USERS[aid]['etime'] = ctime
               USERS[aid]['btime'] = ctime
         cod.close()
         if records: cntadd += add_usage_records(records, cdate)
   

   s = 's' if cntadd > 1 else ''
   PgLOG.pglog("{} COD usage records added for {} entries at {}".format(cntadd, cntall, PgLOG.current_datetime()), PgLOG.LOGWRN)

def add_usage_records(records, date):

   ms = re.match(r'(\d+)-(\d+)-', date)
   if not ms: return 0
   year = ms.group(1)
   quarter = 1 + int((int(ms.group(2)) - 1) / 3)
   cnt = 0

   for aid in records:
      if PgDBI.pgget(USAGE['PGTBL'], '', "aid = '{}' AND date = '{}'".format(aid, date), PgLOG.LGEREX): continue
      record = records[aid]
      if record['email'] == '-':
         record['org_type'] = record['country'] = '-'
      else:
         wuid = PgDBI.check_wuser_wuid(record['email'], date)
         if not wuid: next
         pgrec = PgDBI.pgget("wuser",  "org_type, country", "wuid = {}".format(wuid), PgLOG.LGWNEX)
         if not pgrec: continue
         record['org_type'] = pgrec['org_type']
         record['country'] = pgrec['country']
   
      record['date'] = date
      record['time'] = USERS[aid]['btime']
      record['quarter'] = quarter

      if add_to_allusage(record, year):
         record['aid'] = aid
         record['period'] = access_period(USERS[aid]['etime'], record['time'])
         cnt += PgDBI.pgadd(USAGE['PGTBL'], record, PgLOG.LOGWRN)

   return cnt


def add_to_allusage(pgrec, year):

   record = {'method' : 'COD', 'source' : 'C'}
   for fld in pgrec:
      ms = re.match(r'^(engine|count)$', fld)
      if ms: continue
      record[fld] = pgrec[fld]

   return PgDBI.add_yearly_allusage(year, record)   # change 1 to 0 to stop checking

def cache_users(aid):

   pgrec = PgDBI.pgget("metautil.custom_dap_history", "*", "ID = '{}'".format(aid), PgLOG.LGEREX)

   if pgrec:
      ms = re.search(r'dsnum=(\d+\.\d|[a-z]\d{6});', pgrec['rinfo'])
      if ms:
         dsid = PgUtil.format_dataset_id(ms.group(1))
         USERS[aid]= {'dsid' : dsid, 'email' : pgrec['duser']}
         return 1

   return 0


def access_period(etime, btime):
   
   period = 86400
   
   ms = re.search(r'(\d+):(\d+):(\d+)', etime)
   if ms:
      period = int(ms.group(1))*3600+int(ms.group(2))*60+int(ms.group(3))

   ms = re.search(r'(\d+):(\d+):(\d+)', btime)
   if ms:
      period -= int(ms.group(1))*3600+int(ms.group(2))*60+int(ms.group(3))
   
   return period

#
# call main() to start program
#
if __name__ == "__main__": main()
