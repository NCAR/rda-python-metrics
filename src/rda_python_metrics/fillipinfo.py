#!/usr/bin/env python3
#
###############################################################################
#
#     Title : fillipinfo
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 08/26/2023
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to retrieve ip info and  
#             and fill table ipinfo
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

# the define options for gathering ipinfo data
MONTH = 0x02  # fix data usages for given months
YEARS = 0x04  # fix data usages for given years
NDAYS = 0x08  # fix data usages in recent number of days
MULTI = (MONTH|YEARS)
SINGL = (NDAYS)

IPINFO = {
   'USGTBL'  : ['ipinfo', 'allusage', 'tdsusage'],
   'CDATE' : PgUtil.curdate(),
}

#
# main function to run this program
#
def main():

   inputs = []  # array of input values
   table = None  # table names: ipinfo, allusage, globususage, or tdsusage
   argv = sys.argv[1:]
   topt = option = 0

   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
      elif re.match(r'^-[mNy]$', arg) and option == 0:
         if arg == "-m":
            option = MONTH
         elif arg == "-y":
            option = YEARS
         elif arg == "-N":
            option = NDAYS
      elif arg == "-t":
         topt = 1
      elif re.match(r'^-', arg):
         PgLOG.pglog(arg + ": Invalid Option", PgLOG.LGWNEX)
      elif topt:
         if arg not in IPINFO['USGTBL']:
            PgLOG.pglog("{}: Invalid Table Name; must be in ({})".format(arg, ','.join(IPINFO['USGTBL'])), PgLOG.LGWNEX)
         table = arg
         topt = 0
      elif option&MULTI or option&SINGL and not inputs:
         inputs.append(arg)
      else:
         PgLOG.pglog(arg + ": Invalid Parameter", PgLOG.LGWNEX)

   if not (inputs and table): PgLOG.show_usage('fillipinfo')
   PgDBI.dssdb_dbname()
   PgLOG.cmdlog("fillipinfo {}".format(' '.join(argv)))

   if option&NDAYS:
      curdate = IPINFO['CDATE']
      datelimit = PgUtil.adddate(curdate, 0, 0, -int(inputs[0]))  
      option = MONTH
      inputs = []
      
      while curdate >= datelimit:
         tms = curdate.split('-')
         inputs.append("{}-{}".format(tms[0], tms[1]))
         curdate = PgUtil.adddate(curdate, 0, 0, -int(tms[2]))

   fill_ip_info(option, inputs, table)

   sys.exit(0)

#
# Fill ip info in table dssdb.tdsusage
#
def fill_ip_info(option, inputs, table):

   cntall = 0
   date = None
   for input in inputs:
      if option&NDAYS:
         edate = IPINFO['CDATE']
         date = PgUtil.adddate(edate, 0, 0, -int(input))  
      elif option&MONTH:
         tms = input.split('-')
         date = "{}-{:02}-01".format(tms[0], int(tms[1]))
         edate = PgUtil.enddate(date, 0, 'M')
      elif option&YEARS:
         date = input + "-01-01"
         edate = input + "-12-31"

      while date <= edate:
         func = eval('fix_{}_records'.format(table))
         cntall += func(date)
         date = PgUtil.adddate(date, 0, 0, 1)
   return cntall

def fix_allusage_records(date):

   cnt = 0
   ms = re.match(r'^(\d+)-', date)
   year = ms.group(1)
   table = 'allusage_' + year
   cond = "date = '{}' and org_type = '-'".format(date)
   pgrecs = PgDBI.pgmget(table, 'aidx, email, ip', cond, PgLOG.LGEREX)
   if not pgrecs: return 0
   cnt = len(pgrecs['ip']) if pgrecs else 0
   mcnt = 0
   for i in range(cnt):
      ip = pgrecs['ip'][i]
      email = pgrecs['email'][i]
      ipinfo = PgIPInfo.set_ipinfo(ip)
      if ipinfo:
         record = {'org_type' : ipinfo['org_type'],
                   'country' : ipinfo['country']}
         if not email or re.search(r'-$', email):
            record['email'] =  'unknown@' + ipinfo['hostname']
         mcnt += PgDBI.pgupdt(table, record, "aidx = '{}'".format(pgrecs['aidx'][i]))

   s = 's' if cnt > 1 else ''
   PgLOG.pglog("{}: {} of {} record{} updated for {}".format(table, mcnt, cnt, s, date), PgLOG.LOGWRN)

   return mcnt

def fix_tdsusage_records(date):

   table = 'tdsusage'
   cond = "date = '{}' and org_type = '-'".format(date)
   pgrecs = PgDBI.pgmget(table, 'time, ip', cond, PgLOG.LGEREX)
   if not pgrecs: return 0
   cnt = len(pgrecs['ip']) if pgrecs else 0
   mcnt = 0
   for i in range(cnt):
      ipinfo = PgIPInfo.set_ipinfo(pgrecs['ip'][i])
      if ipinfo:
         record = {'org_type' : ipinfo['org_type'],
                   'country' : ipinfo['country']}
         cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(date, pgrecs['time'][i], pgrecs['ip'][i])
         mcnt += PgDBI.pgupdt(table, record, cond)

   s = 's' if cnt > 1 else ''
   PgLOG.pglog("{}: {} of {} record{} updated for {}".format(table, mcnt, cnt, s, date), PgLOG.LOGWRN)

   return mcnt

def fix_ipinfo_records(date):

   table = 'ipinfo'
   cond = "stat_flag = 'M' and date = '{}'".format(date)
   pgrecs = PgDBI.pgmget(table, 'ip', cond, PgLOG.LGEREX)
   if not pgrecs: return 0
   cnt = len(pgrecs['ip']) if pgrecs else 0
   mcnt = 0
   for i in range(cnt):
      PgIPInfo.set_ipinfo(pgrecs['ip'][i], True)

   mcnt = PgIPInfo.IPINFO['IPUPDT']
   s = 's' if cnt > 1 else ''
   PgLOG.pglog("{}: {} of {} record{} updated".format(table, mcnt, cnt, s), PgLOG.LOGWRN)

   return mcnt

#
# call main() to start program
#
if __name__ == "__main__": main()
