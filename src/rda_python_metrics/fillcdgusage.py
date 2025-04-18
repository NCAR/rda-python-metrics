#!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillcdgusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2025-04-14
#   Purpose : python program to retrieve info from GDEX Postgres database for GDS 
#             file accesses and backup fill table tdsusage in PostgreSQL database dssdb.
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
from rda_python_common import PgSplit
from . import PgIPInfo

USAGE = {
   'TDSTBL'  : "tdsusage",
   'WEBTBL'  : "webusage",
   'CDATE' : PgUtil.curdate(),
}

DSIDS = {
   'ucar.cgd.cesm2.cam6.prescribed_sst_amip' : ['d651010'],
   'ucar.cgd.ccsm4.CLM_LAND_ONLY' : ['d651011'],
   'ucar.cgd.artmip' : ['d651012', 'd651016', 'd651017', 'd651018'],
   'tamip' : ['d651013'],
   'ucar.cgd.ccsm4.CLIVAR_LE' : ['d651014'],
   'ucar.cgd.cesm2.Gettelman_CESM2_ECS' : ['d651015'],
   'ucar.cgd.ccsm4.geomip.ssp5' : ['d651024'],
   'ucar.cgd.ccsm4.IOD-PACEMAKER' : ['d651021'],
   'ucar.cgd.ccsm4.past2k_transient' : ['651023'],
   'ucar.cgd.ccsm4.lowwarming' : ['d651025'],
   'ucar.cgd.ccsm4.CESM_CAM5_BGC_ME' : ['d651000'],
   'ucar.cgd.ccsm4.iTRACE' : ['d651022'],
   'ucar.cgd.ccsm4.so2_geoeng' : ['d651026'],
   'ucar.cgd.ccsm4.cesmLE' : ['d651027'],
   'ucar.cgd.ccsm4.CESM1-CAM5-DP' : ['d651028'],
   'ucar.cgd.ccsm4.amv_lens' : ['d651031'],
   'ucar.cgd.ccsm4.ATL-PACEMAKER' : ['d651032'],
   'ucar.cgd.ccsm4.pac-pacemaker' : ['d651033'],
   'ucar.cgd.ccsm4.SD-WACCM-X_v2.1' : ['d651034'],
   'ucar.cgd.ccsm4.amv_lens' : ['d651035'],
   'ucar.cgd.cesm2.cism_ismip6' : ['d651036'],
   'ucar.cgd.ccsm4.pliomip2' : ['d651037']
}


#
# main function to run this program
#
def main():

   params = {}  # array of input values
   argv = sys.argv[1:]
   opt = None
   
   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
      elif re.match(r'^-[msNy]$', arg):
         opt = arg[1]
         params[opt] = []
      elif re.match(r'^-', arg):
         PgLOG.pglog(arg + ": Invalid Option", PgLOG.LGWNEX)
      elif opt:
         params[opt].append(arg)
      else:
         PgLOG.pglog(arg + ": Value passed in without leading option", PgLOG.LGWNEX)

   if not opt:
      PgLOG.show_usage('fillcdgusage')
   elif 's' not in params:
      PgLOG.pglog("-s: Missing dataset short name to gather CDG metrics", PgLOG.LGWNEX)
   elif len(params) < 2:
      PgLOG.pglog("-(m|N|y): Missing Month, NumberDays or Year to gather CDG metrics", PgLOG.LGWNEX)
      
   
   PgLOG.cmdlog("fillcdgusage {}".format(' '.join(argv)))
   dsids = get_dataset_ids(params['s'])
   if dsids:
      del params['s']
      for o in params:
         dranges = get_date_ranges(o, params[o])
         fill_cdg_usages(dsids, dranges)

   PgLOG.pglog(None, PgLOG.LOGWRN|PgLOG.SNDEML)  # send email out if any

   sys.exit(0)

#
# connect to the gdex database esg-production
#
def gdex_dbname():
   PgDBI.set_scname('esg-production', 'metrics', 'gateway-reader', None, 'sagedbprodalma.ucar.edu')

#
# get datasets
#
def get_dataset_ids(dsnames):

   gdex_dbname()
   dsids = []
   tbname = 'metadata.dataset'
   for dsname in dsnames:
      if dsname not in DSIDS:
         PgLOG.pglog(dsname + ": Unknown CDG dataset short name", PgLOG.LOGWRN)
         continue
      rdaid = DSIDS[dsname]
      pgrec = PgDBI.pgget(tbname, 'id', "short_name = '{}'".format(dsname))
      if not (pgrec and pgrec['id']): continue
      dsid = pgrec['id']
      if dsid in dsids: continue
      dsids.append([dsid, rdaid])
      recursive_dataset_ids(dsid, rdaid, dsids)

   if not dsids: PgLOG.pglog("No Dataset Id identified to gather CDG metrics", PgLOG.LOGWRN)

   return dsids

#
# get dsids recursivley
#
def recursive_dataset_ids(pdsid, rdaid, dsids):

   tbname = 'metadata.dataset'
   pgrecs = PgDBI.pgmget(tbname, 'id', "parent_dataset_id = '{}'".format(pdsid))
   if not pgrecs: return

   for dsid in pgrecs['id']:
      if dsid in dsids: continue
      dsids.append([dsid, rdaid])
      recursive_dataset_ids(dsid, rdaid, dsids)

#
# get the date ranges for given condition
#
def get_date_ranges(option, inputs):

   dranges = []
   for input in inputs:
      # get date range
      dates = []
      if option == 'N':
         dates[1] = USAGE['CDATE']
         dates[0] = PgUtil.adddate(USAGE['CDATE'], 0, 0, -int(input))  
      elif option == 'm':
         tms = input.split('-')
         dates[0] = PgUtil.fmtdate(int(tms[0]), int(tms[1]), 1)
         dates[1] = PgUtil.enddate(dates[0])
      else:
         dates[0] = input + "-01-01"
         dates[1] = input + "-12-31"
      dranges.append(dates)

   return dranges

#
# get file download records for given dsid
#
def get_dsid_records(dsid, dates):

   gdex_dbname()
   tbname = 'metrics.file_download'
   fields = ('date_completed, remote_address, logical_file_size, logical_file_name, file_access_point_uri, user_agent_name, bytes_sent, '
             'subset_file_size, range_request, dataset_file_size, dataset_file_name, dataset_file_file_access_point_uri')
   cond = "dataset_id = '{}' AND completed = True AND date_completed BETWEEN '{}' AND '{}' ORDER BY date_completed".format(dsid, dates[0], dates[1])
   pgrecs = PgDBI.pgmget(tbname, fields, cond)
   PgDBI.dssdb_dbname()

   return pgrecs

#
# Fill TDS usages into table dssdb.tdsusage from cdg access records
#
def fill_cdg_usages(dsids, dranges):

   allcnt = awcnt = atcnt = 0
   for dsid in dsids:
      cdgid = dsid[0]
      rdaid = dsid[1]
      for dates in dranges:
         pgrecs = get_dsid_records(cdgid, dates)
         pgcnt = len(pgrecs['dataset_file_name']) if pgrecs else 0
         if pgcnt == 0:
            PgLOG.pglog("{}: No record found to gather CDG usage between {} and {}".format(rdaid, dates[0], dates[1]), PgLOG.LOGWRN)
            continue
         PgLOG.pglog("{}: gather {} records for CDG usage between {} and {}".format(rdaid, pgcnt, dates[0], dates[1]), PgLOG.LOGWRN)
         tcnt = wcnt = 0
         pwkey = wrec = cdate = None
         trecs = {}
         for i in range(pgcnt):
            if (i+1)%20000 == 0:
               PgLOG.pglog("{}/{}/{} CDG/TDS/WEB records processed to add".format(i, tcnt, wcnt), PgLOG.WARNLG)

            pgrec = PgUtil.onerecord(i, pgrecs)
            dsize = pgrec['bytes_sent']
            if not dsize: continue
            (year, quarter, date, time) = get_record_date_time(pgrec['date_completed'])
            url = pgrec['dataset_file_file_access_point_uri']
            if not url: url = pgrec['file_access_point_uri']
            ip = pgrec['remote_address']
            engine = pgrec['user_agent_name']
            ms = re.search(r'^https://tds.ucar.edu/thredds/(\w+)/', url)
            if ms:
               # tds usage
               method = ms.group(1)
               if pgrec['subset_file_size']:
                  etype = 'S'
               elif pgrec['range_request']:
                  etype = 'R'
               else:
                  etype = 'F'

               if date != cdate:
                  if trecs:
                     tcnt += add_tdsusage_records(year, trecs, cdate)
                     trecs = {}
                  cdate = date
               tkey = "{}:{}:{}:{}".format(ip, rdaid, method, etype)
               if tkey in trecs:
                  trecs[tkey]['size'] += dsize
                  trecs[tkey]['fcount'] += 1
               else:
                  trecs[tkey] = {'ip' : ip, 'dsid' : rdaid, 'date' : cdate, 'time' : time, 'size' : dsize,
                                 'fcount' : 1, 'method' : method, 'etype' : etype, 'engine' : engine}
            else:
               # web usage
               wfile = pgrec['dataset_file_name']
               if not wfile: wfile = pgrec['logic_file_name']
               fsize = pgrec['dataset_file_size']
               if not fsize: fsize = pgrec['logic_file_size']
               method = 'CDP'
               if pgrec['subset_file_size'] or pgrec['range_request'] or dsize < fsize:
                  wkey = "{}:{}:{}".format(ip, rdaid, wfile)
               else:
                  wkey = None
      
               if wrec:
                  if wkey == pwkey:
                     wrec['size'] += dsize
                     continue
                  wcnt += add_webfile_usage(year, wrec)
               wrec = {'ip' : ip, 'dsid' : rdaid, 'wfile' : wfile, 'date' : date,
                       'time' : time, 'quarter' : quarter, 'size' : dsize,
                       'locflag' : 'C', 'method' : method}
               pwkey = wkey
               if not pwkey:
                  wcnt += add_webfile_usage(year, wrec)
                  wrec = None

         if trecs: tcnt += add_tdsusage_records(year, trecs, cdate)
         if wrec: wcnt += add_webfile_usage(year, wrec)
         atcnt += tcnt
         awcnt += wcnt
         allcnt += pgcnt

   PgLOG.pglog("{}/{} TDS/WEB usage records added for {} CDG entries at {}".format(atcnt, awcnt, allcnt, PgLOG.current_datetime()), PgLOG.LOGWRN)


def get_record_date_time(ctime):

   ms = re.search(r'^(\d+)/(\w+)/(\d+) (\d+:\d+:\d+)(\.|$)', str(ctime))
   if ms:
      d = int(ms.group(1))
      m = PgUtil.get_month(ms.group(2))
      q = 1 + int((m-1)/3)
      y = ms.group(3)
      t = ms.group(4)
      return (y, q, "{}-{:02}-{:02}".format(y, m, d), t)
   else:
      PgLOG.pglog("time: Invalid date format", PgLOG.LGEREX)

def add_tdsusage_records(year, records, date):

   cnt = 0
   for key in records:
      record = records[key]
      cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(date, record['time'], record['ip'])
      if PgDBI.pgget(USAGE['TDSTBL'], '', cond, PgLOG.LGEREX): continue
      record['org_type'] = record['country'] = '-'
      ipinfo = PgIPInfo.set_ipinfo(record['ip'])
      if ipinfo:
         record['org_type'] = ipinfo['org_type']
         record['country'] = ipinfo['country']
         record['email'] = 'unknown@' + ipinfo['hostname']

      if add_tds_allusage(year, record):
         cnt += PgDBI.pgadd(USAGE['TDSTBL'], record, PgLOG.LOGWRN)

   PgLOG.pglog("{}: {} TDS usage records added at {}".format(date, cnt, PgLOG.current_datetime()), PgLOG.LOGWRN)

   return cnt


def add_tds_allusage(year, pgrec):

   record = {'method' : 'CDP', 'source' : 'C'}

   for fld in pgrec:
      if re.match(r'^(engine|method|etype|fcount)$', fld): continue
      record[fld] = pgrec[fld]

   return PgDBI.add_yearly_allusage(year, record)

#
# Fill usage of a single online data file into table dssdb.wusage of DSS PgSQL database
#
def add_webfile_usage(year, logrec):

   pgrec = get_wfile_wid(logrec['dsid'], logrec['wfile'])
   if not pgrec: return 0

   table = "{}_{}".format(USAGE['WEBTBL'], year)
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

   if add_web_allusage(year, logrec, wurec):
      return PgDBI.add_yearly_wusage(year, record)
   else:
      return 0

def add_web_allusage(year, logrec, wurec):

   pgrec = {'email' : wurec['email'], 'org_type' : wurec['org_type'], 'country' : wurec['country']}
   pgrec['dsid'] = logrec['dsid']
   pgrec['date'] = logrec['date']
   pgrec['quarter'] = logrec['quarter']
   pgrec['time'] = logrec['time']
   pgrec['size'] = logrec['size']
   pgrec['method'] = logrec['method']
   pgrec['ip'] = logrec['ip']
   pgrec['source'] = 'C'
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
