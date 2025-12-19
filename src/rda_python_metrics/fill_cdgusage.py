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
from time import time as tm
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgFile
from rda_python_common import PgDBI
from rda_python_common import PgSplit
from . import PgIPInfo

USAGE = {
   'TDSTBL'  : "tdsusage",
   'WEBTBL'  : "wusage",
   'CDATE' : PgUtil.curdate(),
}

DSIDS = {
   'pi_cesm2_atm_river_analysis' : ['d010073'],
   'na-cordex' : ['d316009'],
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
   'ucar.cgd.ccsm4.pliomip2' : ['d651037'],
   'ucar.cgd.cesm2-waccm.s2s_hindcasts': ['d651040'],
   'ucar.cgd.CESM1.3_SH_storm_tracks': ['d651044'],
   'ucar.cgd.cesm2.waccm6.ssp245': ['d651045'],
   'ucar.cgd.cesm2.CESM21-CISM2-JG-BG': ['d651046'],
   'ucar.cgd.ccsm4.TC-CESM': ['d651047'],
   'ucar.cgd.cesm2.ISSI_OSSE': ['d651048'],
   'ucar.cgd.ccsm4.SOcean_Eddies_mclong': ['d651049'],
   'ucar.cgd.ccsm.trace': ['d651050'],
   'ucar.cgd.cesm2.waccm.solar': ['d651051'],
   'ucar.cgd.ccsm4.CESM1-CCSM4_mid-Pliocene' : ['d651042'],
   'ucar.cgd.ccsm4.PaleoIF' : ['d651052'],
   'ucar.cgd.ccsm4.b.e11.B20LE_fixedO3' : ['d651053'],
   'ucar.cgd.cesm2.single.forcing.large.ensemble' : ['d651055'],
   'ucar.cgd.cesm2le.output': ['d651056'],
   'ucar.cgd.ccsm4.ARISE-SAI-1.5' : ['d651059'],
   'ucar.cgd.cesm2.s2s_hindcasts': ['d651060'],
   'ucar.cgd.cesm2.s2s_hindcasts.mjo': ['d651061'],
   'ucar.cgd.cesm2.s2s_hindcasts.tc_tracks': ['d651062'],
   'ucar.cgd.cesm2.s2s_hindcasts.cesm2.climo': ['d651063'],
   'ucar.cgd.ccsm4.cesmLME' : ['d651058'],
   'ucar.cgd.ccsm4.GLENS' : ['d651064'],
   'ucar.cgd.ccsm4.CESM2-CISM2-LIGtransient' : ['d651066'],
   'ucar.cgd.cesm2.pacific.pacemaker' : ['d651068'],
   'ucar.cgd.cesm2.tuned.sea.ice.albedo' : ['d651070'],
   'ucar.cgd.cesm2.cmip5.forcing' : ['d651075'],
   'ucar.cgd.cesm2.ssp245.biomass.burning' : ['d651073'],
   'ucar.cgd.cesm2.ssp585.biomass.burning' : ['d651067'],
   'ucar.cgd.cesm1.cldmod': ['d651069'],
   'ucar.cgd.cesm2.marine.biogeochemistry': ['d651071'],
   'ucar.cgd.nw2.mom6': ['d651072'],
   'ucar.cgd.cesm2.cam6.ppe': ['d651076'],
   'ucar.cgd.cesm2.smyle': ['d651065'],
# new added
   'gridded_precip_and_temp' : ['d010078'],
   '29_newman' : ['d010079'],
   'waccm-x.ion.asymmetry' : ['d010081'],
   'NARCCAP' : ['d316015']   
}

ALLIDS = list(DSIDS.keys())

WFILES = {}

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
   dranges = get_date_ranges(params)
   dsids = get_dataset_ids(params['s'])
   if dranges and dsids: fill_cdg_usages(dsids, dranges)
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
      if re.match(r'^all$', dsname, re.I): return get_dataset_ids(ALLIDS)
      if dsname not in DSIDS:
         PgLOG.pglog(dsname + ": Unknown CDG dataset short name", PgLOG.LOGWRN)
         continue
      bt = tm()
      pgrec = PgDBI.pgget(tbname, 'id', "short_name = '{}'".format(dsname))
      if not (pgrec and pgrec['id']): continue
      rdaids = DSIDS[dsname]
      strids = "{}-{}".format(dsname, rdaids)
      cdgid = pgrec['id']
      cdgids = [cdgid]
      ccnt = 1
      ccnt += recursive_dataset_ids(cdgid, cdgids)
      dsids.append([dsname, rdaids, cdgids, strids])
      rmsg = PgLOG.seconds_to_string_time(tm() - bt)
      PgLOG.pglog("{}: Found {} CDG dsid/subdsids in {} at {}".format(strids, ccnt, rmsg, PgLOG.current_datetime()), PgLOG.LOGWRN)

   if not dsids: PgLOG.pglog("No Dataset Id identified to gather CDG metrics", PgLOG.LOGWRN)

   return dsids

#
# get cdgids recursivley
#
def recursive_dataset_ids(pcdgid, cdgids):

   tbname = 'metadata.dataset'
   pgrecs = PgDBI.pgmget(tbname, 'id', "parent_dataset_id = '{}'".format(pcdgid))
   if not pgrecs: return 0

   ccnt = 0
   for cdgid in pgrecs['id']:
      if cdgid in cdgids: continue
      cdgids.append(cdgid)
      ccnt += 1
      ccnt += recursive_dataset_ids(cdgid, cdgids)

   return ccnt

#
# get the date ranges for given condition
#
def get_date_ranges(inputs):

   dranges = []
   for opt in inputs:
      for input in inputs[opt]:
         # get date range
         dates = []
         if opt == 'N':
            dates.append(PgUtil.adddate(USAGE['CDATE'], 0, 0, -int(input)))
            dates.append(USAGE['CDATE'])
         elif opt == 'm':
            tms = input.split('-')
            dates.append(PgUtil.fmtdate(int(tms[0]), int(tms[1]), 1))
            dates.append(PgUtil.enddate(dates[0], 0, 'M'))
         elif opt == 'y':
            dates.append(input + "-01-01")
            dates.append(input + "-12-31")
         if dates: dranges.append(dates)

   return dranges

#
# get file download records for given dsid
#
def get_dsid_records(cdgids, dates, strids):

   gdex_dbname()
   tbname = 'metrics.file_download'
   fields = ('date_completed, remote_address, logical_file_size, logical_file_name, file_access_point_uri, user_agent_name, bytes_sent, '
             'subset_file_size, range_request, dataset_file_size, dataset_file_name, dataset_file_file_access_point_uri')
   dscnt = len(cdgids)
   dscnd = "dataset_id "
   if dscnt == 1:
      dscnd += "= '{}'".format(cdgids[0])
   else:
      dscnd += "IN ('" + "','".join(cdgids) + "')"
   dtcnd = "date_completed BETWEEN '{} 00:00:00' AND '{} 23:59:59'".format(dates[0], dates[1])
   cond = "{} AND {} ORDER BY date_completed".format(dscnd, dtcnd)
   PgLOG.pglog("{}: Query for {} CDG dsid/subdsids between {} and {} at {}".format(strids, dscnt, dates[0], dates[1], PgLOG.current_datetime()), PgLOG.LOGWRN)
   pgrecs = PgDBI.pgmget(tbname, fields, cond)
   PgDBI.dssdb_dbname()

   return pgrecs

#
# Fill TDS usages into table dssdb.tdsusage from cdg access records
#
def fill_cdg_usages(dsids, dranges):

   allcnt = awcnt = atcnt = lcnt = 0
   for dates in dranges:
      for adsid in dsids:
         lcnt += 1
         dsname = adsid[0]
         rdaids = adsid[1]
         getdsid = False if len(rdaids) == 1 else True
         dsid = rdaids[0]
         cdgids = adsid[2]
         strids = adsid[3]
         bt = tm()
         pgrecs = get_dsid_records(cdgids, dates, strids)
         pgcnt = len(pgrecs['dataset_file_name']) if pgrecs else 0
         if pgcnt == 0:
            PgLOG.pglog("{}: No record found to gather CDG usage between {} and {}".format(strids, dates[0], dates[1]), PgLOG.LOGWRN)
            continue
         rmsg = PgLOG.seconds_to_string_time(tm() - bt)
         PgLOG.pglog("{}: Got {} records in {} for processing CDG usage at {}".format(strids, pgcnt, rmsg, PgLOG.current_datetime()), PgLOG.LOGWRN)
         tcnt = wcnt = 0
         pwkey = wrec = cdate = None
         trecs = {}
         bt = tm()
         for i in range(pgcnt):
            if (i+1)%20000 == 0:
               PgLOG.pglog("{}/{}/{} CDG/TDS/WEB records processed to add".format(i, tcnt, wcnt), PgLOG.WARNLG)

            pgrec = PgUtil.onerecord(pgrecs, i)
            wfile = pgrec['dataset_file_name']
            if not wfile:
               wfile = pgrec['logic_file_name']
               if not wfile: continue
            dsize = pgrec['bytes_sent']
            if not dsize: continue
            (year, quarter, date, time) = get_record_date_time(pgrec['date_completed'])
            url = pgrec['dataset_file_file_access_point_uri']
            if not url: url = pgrec['file_access_point_uri']
            ip = pgrec['remote_address']
            engine = pgrec['user_agent_name']
            ms = re.search(r'^https*://tds.ucar.edu/thredds/(\w+)/', url)
            if ms:
               # tds usage
               if getdsid:
                  wfrec = get_wfile_record(rdaids, wfile)
                  if not wfrec: continue
                  dsid = wfrec['dsid']
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
               tkey = "{}:{}:{}:{}".format(ip, dsid, method, etype)
               if tkey in trecs:
                  trecs[tkey]['size'] += dsize
                  trecs[tkey]['fcount'] += 1
               else:
                  iprec =  PgIPInfo.get_missing_ipinfo(ip)
                  if not iprec: continue
                  trecs[tkey] = {'ip' : ip, 'dsid' : dsid, 'date' : cdate, 'time' : time, 'quarter' : quarter,
                                 'size' : dsize, 'fcount' : 1, 'method' : method, 'etype' : etype,
                                 'engine' : engine, 'org_type' : iprec['org_type'], 'country' : iprec['country'],
                                 'region' : iprec['region'], 'email' : iprec['email']}
            else:
               # web usage
               wfrec = get_wfile_record(rdaids, wfile)
               if not wfrec: continue
               if getdsid: dsid = wfrec['dsid']
               fsize = pgrec['dataset_file_size']
               if not fsize: fsize = pgrec['logic_file_size']
               method = 'CDG'
               if pgrec['subset_file_size'] or pgrec['range_request'] or dsize < fsize:
                  wkey = "{}:{}:{}".format(ip, dsid, wfile)
               else:
                  wkey = None
      
               if wrec:
                  if wkey == pwkey:
                     wrec['size'] += dsize
                     continue
                  wcnt += add_webfile_usage(year, wrec)
               wrec = {'ip' : ip, 'dsid' : dsid, 'wid' : wfrec['wid'], 'date' : date,
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
         rmsg = PgLOG.seconds_to_string_time(tm() - bt)
         PgLOG.pglog("{}: {}/{} TDS/WEB usage records added for {} CDG entries in {}".format(strids, atcnt, awcnt, allcnt, rmsg), PgLOG.LOGWRN)

def get_record_date_time(ctime):

   ms = re.search(r'^(\d+)-(\d+)-(\d+) (\d\d:\d\d:\d\d)', str(ctime))
   if ms:
      y = ms.group(1)
      m = int(ms.group(2))
      d = ms.group(3)
      q = 1 + int((m-1)/3)
      t = ms.group(4)
      return (y, q, "{}-{:02}-{}".format(y, m, d), t)
   else:
      PgLOG.pglog(str(ctime) + ": Invalid time format", PgLOG.LGEREX)

def add_tdsusage_records(year, records, date):

   cnt = 0
   for key in records:
      record = records[key]
      cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(date, record['time'], record['ip'])
      if PgDBI.pgget(USAGE['TDSTBL'], '', cond, PgLOG.LGEREX): continue

      if add_tds_allusage(year, record):
         cnt += PgDBI.pgadd(USAGE['TDSTBL'], record, PgLOG.LOGWRN)

   PgLOG.pglog("{}: {} TDS usage records added at {}".format(date, cnt, PgLOG.current_datetime()), PgLOG.LOGWRN)

   return cnt

def add_tds_allusage(year, logrec):

   pgrec = {'method' : 'CDG', 'source' : 'C'}
   pgrec['email'] = logrec['email']
   pgrec['org_type'] = logrec['org_type']
   pgrec['country'] = logrec['country']
   pgrec['region'] = logrec['region']
   pgrec['dsid'] = logrec['dsid']
   pgrec['date'] = logrec['date']
   pgrec['quarter'] = logrec['quarter']
   pgrec['time'] = logrec['time']
   pgrec['size'] = logrec['size']
   pgrec['ip'] = logrec['ip']
   return PgDBI.add_yearly_allusage(year, pgrec)


#
# Fill usage of a single online data file into table dssdb.wusage of DSS PgSQL database
#
def add_webfile_usage(year, logrec):

   table = "{}_{}".format(USAGE['WEBTBL'], year)
   cdate = logrec['date']
   ip = logrec['ip']
   cond = "wid = {} AND method = '{}' AND date_read = '{}' AND time_read = '{}'".format(logrec['wid'], logrec['method'], cdate, logrec['time'])
   if PgDBI.pgget(table, "", cond, PgLOG.LOGWRN): return 0

   wurec =  PgIPInfo.get_wuser_record(ip, cdate)
   if not wurec: return 0

   record = {'wid' : logrec['wid'], 'dsid' : logrec['dsid']}
   record['wuid_read'] = wurec['wuid']
   record['date_read'] = cdate
   record['time_read'] = logrec['time']
   record['size_read'] = logrec['size']
   record['method'] = logrec['method']
   record['locflag'] = logrec['locflag']
   record['ip'] = ip
   record['quarter'] = logrec['quarter']

   if add_web_allusage(year, logrec, wurec):
      return PgDBI.add_yearly_wusage(year, record)
   else:
      return 0

def add_web_allusage(year, logrec, wurec):

   pgrec = {'source' : 'C'}
   pgrec['email'] = wurec['email']
   pgrec['org_type'] = wurec['org_type']
   pgrec['country'] = wurec['country']
   pgrec['region'] = wurec['region']
   pgrec['dsid'] = logrec['dsid']
   pgrec['date'] = logrec['date']
   pgrec['quarter'] = logrec['quarter']
   pgrec['time'] = logrec['time']
   pgrec['size'] = logrec['size']
   pgrec['method'] = logrec['method']
   pgrec['ip'] = logrec['ip']
   return PgDBI.add_yearly_allusage(year, pgrec)

#
# return wfile.wid upon success, 0 otherwise
#
def get_wfile_record(dsids, wfile):

   for dsid in dsids:
      wkey = "{}{}".format(dsid, wfile)
      if wkey in WFILES: return WFILES[wkey]
   wfcond = "wfile LIKE '%{}'".format(wfile)
   pgrec = None
   for dsid in dsids:
      pgrec = PgSplit.pgget_wfile(dsid, "wid", wfcond)
      if pgrec:
         pgrec['dsid'] = dsid
         wkey = "{}{}".format(dsid, wfile)
         WFILES[wkey] = pgrec
         return pgrec

   for dsid in dsids:
      pgrec = PgDBI.pgget("wfile_delete", "wid, dsid", "{} AND dsid = '{}'".format(wfcond, dsid))
      if not pgrec:
         mvrec = PgDBI.pgget("wmove", "wid, dsid", wfcond)
         if mvrec:
            pgrec = PgSplit.pgget_wfile(mvrec['dsid'], "wid", "wid = {}".format(pgrec['wid']))
            if pgrec: pgrec['dsid'] = mvrec['dsid']

   if pgrec: 
      wkey = "{}{}".format(pgrec['dsid'], wfile)
      WFILES[wkey] = pgrec
   return pgrec

#
# call main() to start program
#
if __name__ == "__main__": main()
