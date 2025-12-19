##!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillosdfusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2025-04-01
#   Purpose : python program to retrieve info from weekly OSDF logs 
#             and fill table wusages in PgSQL database dssdb.
# 
#    Github : https://github.com/NCAR/rda-pythn-metrics.git
#
###############################################################################
#
import sys
import re
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgFile
from rda_python_common import PgDBI
from rda_python_common import PgSplit
from . import PgIPInfo

USAGE = {
   'OSDFTBL'  : "osdfusage",
   'OSDFDIR' : PgLOG.PGLOG["GDEXWORK"] + "/zji/osdflogs/",
   'OSDFGET' : 'wget -m -nH -np -nd https://pelicanplatform.org/pelican-access-logs/ncar-access-log/',
   'OSDFLOG' : "{}-cache.log",   # YYYY-MM-DD-cache.log
}

#
# main function to run this program
#
def main():

   params = []  # array of input values
   argv = sys.argv[1:]
   option = None
   datelimits = [None, None]

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
   
   if not (option and params): PgLOG.show_usage('fillosdfusage')

   PgDBI.dssdb_dbname()
   cmdstr = "fillosdfusage {}".format(' '.join(argv))
   PgLOG.cmdlog(cmdstr)
   PgFile.change_local_directory(USAGE['OSDFDIR'])
   filenames = get_log_file_names(option, params, datelimits)
   if filenames:
      fill_osdf_usages(filenames)
   else:
      PgLOG.pglog("No log file found for given command: " + cmdstr, PgLOG.LOGWRN)

   PgLOG.pglog(None, PgLOG.LOGWRN)
   sys.exit(0)

#
# get the log file dates 
#
def get_log_file_names(option, params, datelimits):

   filenames = []
   if option == 'd':
      for pdate in params:
         filenames.append(USAGE['OSDFLOG'].format(pdate))
   else:
      if option == 'N':
         edate = PgUtil.curdate()
         pdate = datelimits[0] = PgUtil.adddate(edate, 0, 0, -int(params[0]))
      else:
         pdate = datelimits[0] = params[0]
         if len(params) > 1:
            edate = datelimits[1] = params[1]
         else:
            edate = PgUtil.curdate()
      while pdate <= edate:
         filenames.append(USAGE['OSDFLOG'].format(pdate))
         pdate = PgUtil.adddate(pdate, 0, 0, 1)

   return filenames

#
# Fill OSDF usages into table dssdb.osdfusage of DSS PgSQL database from osdf access logs
#
def fill_osdf_usages(fnames):

   year = cntall = addall = 0
   for logfile in fnames:
      linfo = PgFile.check_local_file(logfile)
      if not linfo:
         xzfile = logfile + '.xz'
         PgLOG.pgsystem(USAGE['OSDFGET'] + xzfile, 5, PgLOG.LOGWRN)
         linfo = PgFile.check_local_file(xzfile)
         if not linfo:
            PgLOG.pglog("{}: Not exists for Gathering OSDF usage".format(xzfile), PgLOG.LOGWRN)
            continue
         PgFile.compress_local_file(xzfile)
         linfo = PgFile.check_local_file(logfile)
         if not linfo:
            PgLOG.pglog("{}: Error unxz OSDF usage".format(xzfile), PgLOG.LGEREX)
      PgLOG.pglog("{}: Gathering OSDF usage at {}".format(logfile, PgLOG.current_datetime()), PgLOG.LOGWRN)
      osdf = PgFile.open_local_file(logfile)
      if not osdf: continue
      records = {}
      cntadd = entcnt = 0
      while True:
         line = osdf.readline()
         if not line: break
         entcnt += 1
         if entcnt%20000 == 0:
            dcnt = len(records)
            PgLOG.pglog("{}: {}/{} OSDF log entries processed/records added".format(logfile, entcnt, dcnt), PgLOG.WARNLG)

         ms = re.match(r'^\[(\S+)\] \[Objectname:\/ncar\/rda\/([a-z]\d{6})\/\S+\].* \[Site:(\S+)\].* \[Host:(\S+)\].* \[AppInfo:(\S+)\].* \[Read:(\d+)\]', line)
         if not ms: continue
         dt = ms.group(1)
         dsid = ms.group(2)
         site = ms.group(3)
         ip = ms.group(4)
         if ip == 'N/A': ip = PgIPInfo.GIP
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
            (year, quarter, date, time) = get_record_date_time(dt)
            iprec =  PgIPInfo.get_missing_ipinfo(ip)
            if not iprec: continue
            records[key] = {'ip' : iprec['ip'], 'dsid' : dsid, 'date' : date, 'time' : time, 'quarter' : quarter,
                            'size' : size, 'fcount' : 1, 'method' : method, 'engine' : engine,
                            'org_type' : iprec['org_type'], 'country' : iprec['country'],
                            'region' : iprec['region'], 'email' : iprec['email'], 'site' : site}
      osdf.close()
      if records: cntadd = add_usage_records(records, year)
      PgLOG.pglog("{}: {} OSDF usage records added for {} entries at {}".format(logfile, cntadd, entcnt, PgLOG.current_datetime()), PgLOG.LOGWRN)
      cntall += entcnt
      if cntadd:
         addall += cntadd
         if addall > cntadd:
            PgLOG.pglog("{} OSDF usage records added for {} entries at {}".format(addall, cntall, PgLOG.current_datetime()), PgLOG.LOGWRN)


def get_record_date_time(ctime):

   ms = re.search(r'^(\d+)-(\d+)-(\d+)T([\d:]+)\.', ctime)
   if ms:
      y = ms.group(1)
      m = int(ms.group(2))
      d = int(ms.group(3))
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
      if PgDBI.pgget(USAGE['OSDFTBL'], '', cond, PgLOG.LGEREX): continue
      if add_to_allusage(year, record):
         cnt += PgDBI.pgadd(USAGE['OSDFTBL'], record, PgLOG.LOGWRN)

   return cnt

def add_to_allusage(year, pgrec):

   record = {'source' : 'P'}
   flds = ['ip', 'dsid', 'date', 'time', 'quarter', 'size', 'method',
           'org_type', 'country', 'region', 'email']

   for fld in flds:
      record[fld] = pgrec[fld]

   return PgDBI.add_yearly_allusage(year, record)

#
# call main() to start program
#
if __name__ == "__main__": main()
