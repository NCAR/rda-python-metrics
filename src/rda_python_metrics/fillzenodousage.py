#!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillzenodousage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2025-04-14
#   Purpose : python program to retrieve info from GDEX Postgres database for GDEX 
#             file accesses and backup fill table gdexzenodo in PostgreSQL database dssdb.
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
   'ZNDTBL'  : "gdexzenodo",
   'CDATE' : PgUtil.curdate(),
}

DSIDS = {
   "498" : "15760289",
   "386_ahijevych" : "15501153",
   "66_oclifton" : "15501155",
   "196_mayernik" : "15501157",
   "83_heyms1" : "15501159",
   "405_qwu" : "15501163",
   "WACCMX_DART_Hindcast" : "15501165",
   "234_buchholz" : "15501167",
   "365_barthm" : "15501171",
   "Polar_Cap_HIWIND_observation_and_TIEGCM_simulations" : "15501173",
   "266_xuguang" : "15501175",
   "277_lqian" : "15501177",
   "Ocean_MHT_Values" : "15501181",
   "92_xuguang" : "15501184",
   "118_nickp" : "15501186",
   "398_kunwu" : "15501188",
   "107_siyuan" : "15501190",
   "274_gaubert" : "15501192",
   "301_ldong" : "15501194",
   "GRL_Kurowski_al_2019" : "15501196",
   "112_fjudt" : "15501201",
   "14_schuster" : "15501203",
   "102_abaker" : "15501205",
   "402_qwu" : "15501207",
   "324_lqian" : "15501209",
   "Response_of_the_F2-region_Ionosphere_to_the_21_August_2017_Solar_Eclipse_at_Millstone_Hill" : "15501211",
   "362_kunwu" : "15501213",
   "LFM-TIEGCM-RCM_Simulation" : "15501216",
   "140_xuguang" : "15501221",
   "240_ldong" : "15501223",
   "93_sallyz" : "15501229",
   "452" : "15501231",
   "318_ldong" : "15501233",
   "161_ldong" : "15501237",
   "288_voemel" : "15501239",
   "160_xuguang" : "15501241",
   "CO_Flux_Inversion_Attribution" : "15501243",
   "404_buchholz" : "15501245",
   "193_wily" : "15501247",
   "471" : "15501249",
   "323_grabow" : "15501251",
   "2019_GrandChallengeIT_paper" : "15501253",
   "203_patton" : "15501255",
   "450" : "15501259",
   "359_wwieder" : "15501261",
   "205_xuguang" : "15501265",
   "218_xuguang" : "15501267",
   "236_xuguang" : "15501269",
   "211_fjudt" : "15501273",
   "2018_Schmidt_JGR_Volcanic_RF" : "15501277",
   "438" : "15501279",
   "267_fredc" : "15501282",
   "321_patton" : "15501286",
   "467" : "15501294",
   "145_lqian" : "15501296",
   "317_jaredlee" : "15501298",
   "WACCMX_2005_Solar_Flare" : "15501305",
   "369_buchholz" : "15501313",
   "148_bjohns" : "15501319",
   "158_asphilli" : "15501326",
   "VAPOR_Sample_Data" : "15501333",
   "188b_oleson" : "15501339",
   "206_grabow" : "15501349",
   "127_cweeks" : "15501358",
   "2019_Ionosphere_Thermosphere_Qian" : "15501375",
   "391_kim" : "15501388",
   "200_fredc" : "15501403",
   "147_miesch" : "15501412",
   "141_maute" : "15501419",
   "147b_jcsda" : "15501432",
   "283_dll" : "15501444",
   "78_clyne_wrf" : "15501451",
   "345_wwieder" : "15501470",
   "221_mclong" : "15501488",
   "257_ottobli" : "15501516",
   "287_qwu" : "15501551",
   "400_qwu" : "15501569",
   "184_jjang" : "15501603",
   "197_islas" : "15501620",
   "ftir" : "15501660",
   "282_fasullo" : "15501697",
   "139_oclifton" : "15501795",
   "348_wwieder" : "15501824",
   "451" : "15501860",
   "188a_oleson" : "15501878",
   "173A_dcherian" : "15501913",
   "297_qingyu" : "15501946",
   "523" : "15501974",
   "472" : "15502021",
   "138_maute" : "15502102",
   "387_jay" : "15502178",
   "jedi-skylab" : "15502247",
   "CLM5_Sensitivity_Analyses" : "15502308",
   "531" : "15502409",
   "327_qwu" : "15502530",
   "94_nickp" : "15502666",
   "camels" : "15529996",
   "68_rschwant" : "15502739",
   "WACCM_VolcAerProp" : "15503247",
   "213_fasullo" : "15503556",
   "263_nystrom" : "15504044",
   "239_fasullo" : "15504166",
   "292_qingyu" : "15504276",
   "294_maute" : "15504555",
   "209_yeager" : "15504665",
   "440" : "15504780",
   "207_gunterl" : "15504857",
   "172_cdswk" : "15505157",
   "285_qingyu" : "15505262",
   "422" : "15505355",
   "120_maute" : "15505595",
   "69_maute" : "15507025",
   "63_maute" : "15507365",
   "280_islas" : "15507449",
   "JAMES_2019MS001833" : "15507514",
   "165_nickp" : "15507754",
   "510" : "15507947",
   "96_morrison" : "15508039",
   "164_bukovsky" : "15508226",
   "378_caron" : "15508458",
   "483" : "15508746",
   "144_grabow" : "15508914",
   "188c_oleson" : "15509127",
   "204_ajahn" : "15510016",
   "72_kdagon" : "15511424",
   "302_yeager" : "15511789",
   "86_morrison" : "15513137",
   "259_jimenez" : "15514297"
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
      PgLOG.show_usage('fillzenodousage')
   elif 's' not in params:
      PgLOG.pglog("-s: Missing dataset short name to gather ZENODO metrics", PgLOG.LGWNEX)
   elif len(params) < 2:
      PgLOG.pglog("-(m|N|y): Missing Month, NumberDays or Year to gather ZENODO metrics", PgLOG.LGWNEX)
      
   
   PgLOG.cmdlog("fillzenodousage {}".format(' '.join(argv)))
   dranges = get_date_ranges(params)
   dsids = get_dataset_ids(params['s'])
   if dranges and dsids: fill_zenodo_usages(dsids, dranges)
   PgLOG.pglog(None, PgLOG.LOGWRN|PgLOG.SNDEML)  # send email out if any

   sys.exit(0)

#
# connect to the gdex database esg-production
#
def gdex_dbname():
   PgDBI.set_scname('gdex-production', 'metrics', 'gateway-reader', None, 'sagedbprodalma.ucar.edu')

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
         PgLOG.pglog(dsname + ": Unknown ZENODO dataset short name", PgLOG.LOGWRN)
         continue
      bt = tm()
      pgrec = PgDBI.pgget(tbname, 'id', "short_name = '{}'".format(dsname))
      if not (pgrec and pgrec['id']): continue
      zndid = DSIDS[dsname]
      strids = "{}-{}".format(dsname, zndid)
      gdexid = pgrec['id']
      gdexids = [gdexid]
      ccnt = 1
      ccnt += recursive_dataset_ids(gdexid, gdexids)
      dsids.append([dsname, zndid, gdexids, strids])
      rmsg = PgLOG.seconds_to_string_time(tm() - bt)
      PgLOG.pglog("{}: Found {} GDEX dsid/subdsids in {} at {}".format(strids, ccnt, rmsg, PgLOG.current_datetime()), PgLOG.LOGWRN)

   if not dsids: PgLOG.pglog("No Dataset Id identified to gather GDEX metrics", PgLOG.LOGWRN)

   return dsids

#
# get gdexids recursivley
#
def recursive_dataset_ids(pgdexid, gdexids):

   tbname = 'metadata.dataset'
   pgrecs = PgDBI.pgmget(tbname, 'id', "parent_dataset_id = '{}'".format(pgdexid))
   if not pgrecs: return 0

   ccnt = 0
   for gdexid in pgrecs['id']:
      if gdexid in gdexids: continue
      gdexids.append(gdexid)
      ccnt += 1
      ccnt += recursive_dataset_ids(gdexid, gdexids)

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
def get_dsid_records(gdexids, dates, strids):

   gdex_dbname()
   tbname = 'metrics.file_download'
   fields = ('date_completed, remote_address, logical_file_size, logical_file_name, file_access_point_uri, user_agent_name, bytes_sent, '
             'subset_file_size, range_request, dataset_file_size, dataset_file_name, dataset_file_file_access_point_uri')
   dscnt = len(gdexids)
   dscnd = "dataset_id "
   if dscnt == 1:
      dscnd += "= '{}'".format(gdexids[0])
   else:
      dscnd += "IN ('" + "','".join(gdexids) + "')"
   dtcnd = "date_completed BETWEEN '{} 00:00:00' AND '{} 23:59:59'".format(dates[0], dates[1])
   cond = "{} AND {} ORDER BY date_completed".format(dscnd, dtcnd)
   PgLOG.pglog("{}: Query for {} GDEX dsid/subdsids between {} and {} at {}".format(strids, dscnt, dates[0], dates[1], PgLOG.current_datetime()), PgLOG.LOGWRN)
   pgrecs = PgDBI.pgmget(tbname, fields, cond)
   PgDBI.dssdb_dbname()

   return pgrecs

#
# Fill ZND usages into table dssdb.tdsusage from gdex access records
#
def fill_zenodo_usages(dsids, dranges):

   allcnt = awcnt = azcnt = lcnt = 0
   for dates in dranges:
      for dsid in dsids:
         lcnt += 1
         dsname = dsid[0]
         zndid = dsid[1]
         gdexids = dsid[2]
         strids = dsid[3]
         bt = tm()
         pgrecs = get_dsid_records(gdexids, dates, strids)
         pgcnt = len(pgrecs['dataset_file_name']) if pgrecs else 0
         if pgcnt == 0:
            PgLOG.pglog("{}: No record found to gather GDEX usage between {} and {}".format(strids, dates[0], dates[1]), PgLOG.LOGWRN)
            continue
         rmsg = PgLOG.seconds_to_string_time(tm() - bt)
         PgLOG.pglog("{}: Got {} records in {} for processing GDEX usage at {}".format(strids, pgcnt, rmsg, PgLOG.current_datetime()), PgLOG.LOGWRN)
         zcnt = 0
         pwkey = wrec = cdate = None
         zrecs = {}
         bt = tm()
         for i in range(pgcnt):
            if (i+1)%20000 == 0:
               PgLOG.pglog("{}/{} GDEX/ZND records processed to add".format(i, zcnt), PgLOG.WARNLG)

            pgrec = PgUtil.onerecord(pgrecs, i)
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
               if pgrec['subset_file_size']:
                  etype = 'S'
               elif pgrec['range_request']:
                  etype = 'R'
               else:
                  etype = 'F'
               method = 'TDS-' + etype
            else:
               # web usage
               method = 'WEB'

            if date != cdate:
               if zrecs:
                  zcnt += add_zusage_records(zrecs, cdate)
                  zrecs = {}
               cdate = date
            zkey = "{}:{}:{}".format(ip, zndid, method)
            if zkey in zrecs:
               zrecs[zkey]['size'] += dsize
               zrecs[zkey]['fcount'] += 1
            else:
               iprec =  PgIPInfo.get_missing_ipinfo(ip)
               if not iprec: continue
               zrecs[zkey] = {'ip' : ip, 'zdsid' : zndid, 'date' : cdate, 'time' : time, 'quarter' : quarter,
                              'size' : dsize, 'fcount' : 1, 'method' : method}

         if zrecs: zcnt += add_zusage_records(zrecs, cdate)
         azcnt += zcnt
         allcnt += pgcnt
         rmsg = PgLOG.seconds_to_string_time(tm() - bt)
         PgLOG.pglog("{}: {} usage records added for {} ZENODO entries in {}".format(strids, azcnt, allcnt, rmsg), PgLOG.LOGWRN)

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

def add_zusage_records(records, date):

   cnt = 0
   for key in records:
      record = records[key]
      cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(date, record['time'], record['ip'])
      if PgDBI.pgget(USAGE['ZNDTBL'], '', cond, PgLOG.LGEREX): continue

      cnt += PgDBI.pgadd(USAGE['ZNDTBL'], record, PgLOG.LOGWRN)

   PgLOG.pglog("{}: {} ZND usage records added at {}".format(date, cnt, PgLOG.current_datetime()), PgLOG.LOGWRN)

   return cnt

#
# call main() to start program
#
if __name__ == "__main__": main()
