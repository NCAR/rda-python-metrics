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
   'PGTBL'  : "wusage",
   'AWSDIR' : PgLOG.PGLOG["TRANSFER"] + "/AWSera5log",
   'AWSLOG' : "{}/{}-00-00-00-*",
   'PFMT'   : "YYYY/MM/DD"
}

DSIDS = {'nsf-ncar-era5' : PgUtil.format_dataset_id('d633000')}

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

   filenames = []
   if option == 'd':
      for dt in params:
         pdate = PgUtil.format_date(dt)
         pd = PgUtil.format_date(pdate, USAGE['PFMT'])
         fname = USAGE['AWSLOG'].format(pd, pdate)
         fnames = glob.glob(fname)
         if fnames: filenames.extend(sorted(fnames))
   else:
      if option == 'N':
         edate = PgUtil.curdate()
         pdate = PgUtil.adddate(edate, 0, 0, -int(params[0]))
      else:
         pdate = PgUtil.format_date(params[0])
         if len(params) > 1:
            edate = PgUtil.format_date(params[1])
         else:
            edate = PgUtil.curdate()
      while pdate <= edate:
         pd = PgUtil.format_date(pdate, USAGE['PFMT'])
         fname = USAGE['AWSLOG'].format(pd, pdate)
         fnames = glob.glob(fname)
         if fnames: filenames.extend(sorted(fnames))
         pdate = PgUtil.adddate(pdate, 0, 0, 1)

   return filenames

#
# Fill AWS usages into table dssdb.awsusage of DSS PgSQL database from aws access logs
#
def fill_aws_usages(fnames):

   cntall = addall = 0
   fcnt = len(fnames)
   for logfile in fnames:
      if not op.isfile(logfile):
         PgLOG.pglog("{}: Not exists for Gathering AWS usage".format(logfile), PgLOG.LOGWRN)
         continue
      PgLOG.pglog("Gathering usage info from {} at {}".format(logfile, PgLOG.current_datetime()), PgLOG.LOGWRN)
      aws = PgFile.open_local_file(logfile)
      if not aws: continue
      ptime = ''
      record = {}
      cntadd = entcnt = 0
      pkey = None
      while True:
         line = aws.readline()
         if not line: break
         entcnt += 1
         if entcnt%10000 == 0:
            PgLOG.pglog("{}: {}/{} AWS log entries processed/records added".format(logfile, entcnt, cntadd), PgLOG.WARNLG)

         ms = re.match(r'^\w+ ([\w-]+) \[(\S+).*\] ([\d\.]+) .+ REST\.GET\.OBJECT (\S+) "GET.+" (200|206) - (\d+) (\d+) .* ".+" "(.+)" ', line)
         if not ms: continue
         values = list(ms.groups())
         if values[0] not in DSIDS: continue
         dsid = DSIDS[values[0]]
         size = int(values[5])
         fsize = int(values[6])
         if fsize < 100: continue  # ignore small files
         ip = values[2]
         wfile = values[3]
         stat = values[4]
         engine = values[7]
         (year, quarter, date, time) = get_record_date_time(values[1])
         locflag = 'A'

         if re.match(r'^aiobotocore', engine, re.I):
            method = "AIOBT"
         elif re.match(r'^rclone', engine, re.I):
            method = "RCLON"
         elif re.match(r'^python', engine, re.I):
            method = "PYTHN"
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
      aws.close()
      cntall += entcnt
      addall += cntadd
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

#
# Fill usage of a single online data file into table dssdb.wusage of DSS PgSQL database
#
def add_file_usage(year, logrec):

   pgrec = get_wfile_wid(logrec['dsid'], logrec['wfile'])
   if not pgrec: return 0

   table = "{}_{}".format(USAGE['PGTBL'], year)
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
   pgrec['source'] = 'A'
   return PgDBI.add_yearly_allusage(year, pgrec)

#
# return wfile.wid upon success, 0 otherwise
#
def get_wfile_wid(dsid, wfile):

   dscond = "dsid = '{}' AND wfile = '{}'".format(dsid, wfile) 
   pgrec = PgDBI.pgget("wfile", "*", dscond)

   if not pgrec:
      pgrec = PgDBI.pgget("wmove", "wid, dsid", dscond)
      if pgrec:
         pgrec = PgDBI.pgget("wfile", "*", "wid = {}".format(pgrec['wid']))
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
