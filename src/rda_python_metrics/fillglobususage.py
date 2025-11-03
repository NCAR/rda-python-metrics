##!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillglobususage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/11/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to retrieve info from Globus logs 
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
from rda_python_common import PgSplit
from . import PgIPInfo

USAGE = {
   'PGTBL'  : "wusage",
   'GBSDIR' : PgLOG.PGLOG["GDEXWORK"] + "/logs/gridftp/",
   'GBSLOG' : "access_log_gridftp0{}_{}",
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
      ms = re.match(r'^-(b|d|f|p|N)$', arg)
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
   
   if not (option and params): PgLOG.show_usage('fillglobususage')

   PgDBI.dssdb_dbname()
   cmdstr = "fillglobususage {}".format(' '.join(argv))
   PgLOG.cmdlog(cmdstr)
   PgFile.change_local_directory(USAGE['GBSDIR'])
   filenames = get_log_file_names(option, params, datelimits)
   if filenames:
      fill_globus_usages(filenames, datelimits)
   else:
      PgLOG.pglog("No log file found for given command: " + cmdstr, PgLOG.LOGWRN)

   PgLOG.pglog(None, PgLOG.LOGWRN)
   sys.exit(0)

#
# get the log file dates 
#
def get_log_file_names(option, params, datelimits):

   filenames = []
   if option == 'f':
      filenames = params
   elif option == 'd':
      for pdate in params:
         fdate = PgUtil.format_date(pdate, 'MMDDYYYY')
         fname = USAGE['GBSLOG'].format('?', fdate)
         fnames = glob.glob(fname)
         if fnames: filenames.extend(sorted(fnames))
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
         fdate = PgUtil.format_date(pdate, 'MMDDYYYY')
         fname = USAGE['GBSLOG'].format('?', fdate)
         fnames = glob.glob(fname)
         if fnames: filenames.extend(sorted(fnames))
         pdate = PgUtil.adddate(pdate, 0, 0, 1)

   return filenames

#
# Fill Globus usages into table dssdb.globususage of DSS PgSQL database from globus access logs
#
def fill_globus_usages(fnames, datelimits):

   cntall = addall = 0

   fcnt = len(fnames)
   for logfile in fnames:
      if not op.isfile(logfile):
         PgLOG.pglog("{}: Not exists for Gathering Globus usage".format(logfile), PgLOG.LOGWRN)
         continue
      PgLOG.pglog("Gathering usage info from {} at {}".format(logfile, PgLOG.current_datetime()), PgLOG.LOGWRN)
      globus = PgFile.open_local_file(logfile)
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
            PgLOG.pglog("{}: {}/{} Globus log entries processed/records added".format(logfile, entcnt, cntadd), PgLOG.WARNLG)

         ms = re.match(r'^([\d\.]+)\s.*\s+\[(\S+).*"GET\s+/(ds\d\d\d\.\d|[a-z]\d{6})/(\S+)\s.*\s(200|206)\s+(\d+)\s+"(\S+)"\s+"(.+)"$', line)
         if not ms: continue
         size = int(ms.group(6))
         if size < 100: continue  # ignore small files
         ip = ms.group(1)
         dsid = PgUtil.format_dataset_id(ms.group(3))
         wfile = ms.group(4)
         stat = ms.group(5)
         sline = ms.group(7)
         engine = ms.group(8)
         (year, quarter, date, time) = get_record_date_time(ms.group(2))
         if datelimits[0] and date < datelimits[0]: continue
         if datelimits[1] and date > datelimits[1]: continue
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
            cntadd += add_file_usage(year, record)
         record = {'ip' : ip, 'dsid' : dsid, 'wfile' : wfile, 'date' : date,
                   'time' : time, 'quarter' : quarter, 'size' : size,
                   'locflag' : locflag, 'method' : method}
         pkey = key
         if not pkey:
            cntadd += add_file_usage(year, record)
            record = None
      if record: cntadd += add_file_usage(year, record)
      globus.close()
      cntall += entcnt
      addall += cntadd
      PgLOG.pglog("{} Globus usage records added for {} entries at {}".format(addall, cntall, PgLOG.current_datetime()), PgLOG.LOGWRN)


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

#
# Fill usage of a single online data file into table dssdb.wusage of DSS PgSQL database
#
def add_file_usage(year, logrec):

   pgrec = get_wfile_wid(logrec['dsid'], logrec['wfile'])
   if not pgrec: return 0

   table = "{}_{}".format(USAGE['PGTBL'], year)
   cond = "wid = {} AND method = '{}' AND date_read = '{}' AND time_read = '{}'".format(pgrec['wid'], logrec['method'], logrec['date'], logrec['time'])
   if PgDBI.pgget(table, "", cond, PgLOG.LOGWRN): return 0

   wurec =  PgIPInfo.get_wuser_record(logrec['ip'], logrec['date'])
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

   if add_to_allusage(year, logrec, wurec):
      return PgDBI.add_yearly_wusage(year, record)
   else:
      return 0

def add_to_allusage(year, logrec, wurec):

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
   return PgDBI.add_yearly_allusage(year, pgrec)

#
# return wfile.wid upon success, 0 otherwise
#
def get_wfile_wid(dsid, wfile):

   wfcond = "wfile = '{}'".format(wfile) 
   pgrec = PgSplit.pgget_wfile(dsid, "*", wfcond)
   if pgrec:
      pgrec['dsid'] = dsid
   else:
      pgrec = PgDBI.pgget("wfile_delete", "*", "{} AND dsid = '{}'".format(wfcond, dsid))
      if not pgrec:
         pgrec = PgDBI.pgget("wmove", "wid, dsid", wfcond)
         if pgrec:
            pgrec = PgSplit.pgget_wfile(pgrec['dsid'], "*", "wid = {}".format(pgrec['wid']))
            if pgrec: pgrec['dsid'] = dsid

   return pgrec

#
# call main() to start program
#
if __name__ == "__main__": main()
