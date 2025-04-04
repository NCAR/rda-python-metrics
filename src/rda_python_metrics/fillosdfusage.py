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
   'OSDFTBL'  : "wusage",
   'OSDFDIR' : PgLOG.PGLOG["DSSDATA"] + "/work/zji/osdflogs/",
   'OSDFGET' : 'wget -m -nH -np -nd https://pelicanplatform.org/pelican-access-logs/ncar-access-log/',
   'OSDFLOG' : "{}.log",   # YYYY-MM-DD.log
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
      fill_osdf_usages(filenames, datelimits)
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
         pdays = PgUtil.get_weekday(pdate)
         if pdays > 0:
            PgLOG.pglog(pdate + ": Skip a Non-Sunday date", PgLOG.LOGWRN)
            continue
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
      pdays = PgUtil.get_weekday(pdate)
      if pdays > 0: pdate = PgUtil.adddate(pdate, 0, 0, 7-pdays)
      while pdate <= edate:
         filenames.append(USAGE['OSDFLOG'].format(pdate))
         pdate = PgUtil.adddate(pdate, 0, 0, 7)

   return filenames

#
# Fill OSDF usages into table dssdb.osdfusage of DSS PgSQL database from osdf access logs
#
def fill_osdf_usages(fnames, datelimits):

   cntall = addall = 0

   fcnt = len(fnames)
   for logfile in fnames:
      PgLOG.pgsystem(USAGE['OSDFGET'] + logfile, 5, PgLOG.LOGWRN)
      linfo = PgFile.check_local_file(logfile)
      if not linfo:
         PgLOG.pglog("{}: Not exists for Gathering OSDF usage".format(logfile), PgLOG.LOGWRN)
         continue
      if linfo['data_size'] == 0:
         PgLOG.pglog("{}: Empty log for Gathering OSDF usage".format(logfile), PgLOG.LOGWRN)
         continue
      PgLOG.pglog("Gathering usage info from {} at {}".format(logfile, PgLOG.current_datetime()), PgLOG.LOGWRN)
      osdf = PgFile.open_local_file(logfile)
      if not osdf: continue
      cntadd = entcnt = 0
      pkey = None
      while True:
         line = osdf.readline()
         if not line: break
         entcnt += 1
         if entcnt%10000 == 0:
            PgLOG.pglog("{}: {}/{} OSDF log entries processed/records added".format(logfile, entcnt, cntadd), PgLOG.WARNLG)

         ms = re.match(r'^\[(\S+)\] \[Objectname:\/ncar\/rda\/([a-z]\d{6})\/(\S+)\] \[Host:(\S+)\] \[Server:(\S+)\] \[Read:(\d+)\]', line)
         if not ms: continue
         size = int(ms.group(6))
         if size < 100: continue  # ignore small files
         ip = ms.group(4)
         dsid = PgUtil.format_dataset_id(ms.group(2))
         wfile = ms.group(3)
         engine = ms.group(5)
         
         (year, quarter, date, time) = get_record_date_time(ms.group(1))
         if datelimits[0] and date < datelimits[0]: continue
         if datelimits[1] and date > datelimits[1]: continue
         locflag = 'C'
         method = "OSDF"

         record = {'ip' : ip, 'dsid' : dsid, 'wfile' : wfile, 'date' : date,
                   'time' : time, 'quarter' : quarter, 'size' : size,
                   'locflag' : locflag, 'method' : method}
         cntadd += add_file_usage(year, record)
      osdf.close()
      cntall += entcnt
      addall += cntadd
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

#
# Fill usage of a single online data file into table dssdb.wusage of DSS PgSQL database
#
def add_file_usage(year, logrec):

   pgrec = get_wfile_wid(logrec['dsid'], logrec['wfile'])
   if not pgrec: return 0

   table = "{}_{}".format(USAGE['OSDFTBL'], year)
   cond = "wid = {} AND method = '{}' AND date_read = '{}' AND time_read = '{}'".format(pgrec['wid'], logrec['method'], logrec['date'], logrec['time'])
   if PgDBI.pgget(table, "", cond, PgLOG.LOGWRN): return 0

   wurec =  get_wuser_record(logrec['ip'], logrec['date'])
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

   pgrec = {'email' : wurec['email'], 'org_type' : wurec['org_type'], 'country' : wurec['country']}
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

# return wuser record upon success, None otherwise
def get_wuser_record(ip, date):

   ipinfo = PgIPInfo.set_ipinfo(ip)
   if not ipinfo: return None

   record = {'org_type' : ipinfo['org_type'], 'country' : ipinfo['country']}
   email = 'unknown@' + ipinfo['hostname']
   emcond = "email = '{}'".format(email)
   flds = 'wuid, email, org_type, country, start_date'   
   pgrec = PgDBI.pgget("wuser", flds, emcond, PgLOG.LOGERR)
   if pgrec:
      if PgUtil.diffdate(pgrec['start_date'], date) > 0:
         pgrec['start_date'] = record['start_date'] = date
         PgDBI.pgupdt('wuser', record, emcond)
      return pgrec

   # now add one in
   record['email'] = email
   record['stat_flag'] = 'A'
   record['start_date'] = date
   wuid = PgDBI.pgadd("wuser", record, PgLOG.LOGERR|PgLOG.AUTOID)
   if wuid:
      record['wuid'] = wuid
      PgLOG.pglog("{} Added as wuid({})".format(email, wuid), PgLOG.LGWNEM)
      return record

   return None

#
# call main() to start program
#
if __name__ == "__main__": main()
