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
DATES = 0x01  # fix data usages for given dates
MONTH = 0x02  # fix data usages for given months
YEARS = 0x04  # fix data usages for given years
NDAYS = 0x08  # fix data usages in recent number of days
MULTI = (DATES|MONTH|YEARS)
SINGL = (NDAYS)

IPINFO = {
   'USGTBL'  : ['ipinfo', 'wuser', 'allusage', 'codusage', 'tdsusage'],
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
      elif re.match(r'^-[dmNy]$', arg) and option == 0:
         if arg == "-d":
            option = DATES
         elif arg == "-m":
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

   fill_ip_info(option, inputs, table)

   sys.exit(0)

#
# Fill ip info in table dssdb.tdsusage
#
def fill_ip_info(option, inputs, table):

   cntall = 0
   func = eval('fix_{}_records'.format(table))
   for input in inputs:
      if option&NDAYS:
         edate = IPINFO['CDATE']
         date = PgUtil.adddate(edate, 0, 0, -int(input))
      elif option&DATES:
         edate = date = input
      elif option&MONTH:
         tms = input.split('-')
         date = "{}-{:02}-01".format(tms[0], int(tms[1]))
         edate = PgUtil.enddate(date, 0, 'M')
      else:
         date = input + "-01-01"
         edate = input + "-12-31"
      while True:
         (ndate, cond) = get_next_date(date, edate)
         cntall += func(date, cond)
         if ndate >= edate: break
         date = PgUtil.adddate(ndate, 0, 0, 1)

   if cntall > 2:
      PgLOG.pglog("{}: Total {} records updated".format(table, cntall), PgLOG.LOGWRN)

def get_next_date(date, edate):

   if date < edate:
      ndate = PgUtil.enddate(date, 0, 'M')
      if ndate < edate: edate = ndate
   if date < edate:
      cond = f"BETWEEN '{date}' AND '{edate}'"
   else:
      cond = f"= '{date}'"

   return (edate, cond)


def fix_allusage_records(date, cnd):

   cnt = 0
   ms = re.match(r'^(\d+)-', date)
   year = ms.group(1)
   table = 'allusage_' + year
   cond = f"date {cnd} AND region IS NULL"
   pgrecs = PgDBI.pgmget(table, 'aidx, email, ip', cond, PgLOG.LGEREX)
   if not pgrecs: return 0
   cnt = len(pgrecs['ip']) if pgrecs else 0
   mcnt = 0
   for i in range(cnt):
      record = PgIPInfo.get_missing_ipinfo(pgrecs['ip'][i], pgrecs['email'][i])
      if record:
         mcnt += PgDBI.pgupdt(table, record, "aidx = '{}'".format(pgrecs['aidx'][i]))

   s = 's' if cnt > 1 else ''
   PgLOG.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for date {cnd}", PgLOG.LOGWRN)

   return mcnt

def fix_tdsusage_records(date, cnd):

   table = 'tdsusage'
   cond = f"date {cnd} AND region IS NULL"
   pgrecs = PgDBI.pgmget(table, 'date, time, email, ip', cond, PgLOG.LGEREX)
   if not pgrecs: return 0
   cnt = len(pgrecs['ip']) if pgrecs else 0
   mcnt = 0
   for i in range(cnt):
      ip = pgrecs['ip'][i]
      record = PgIPInfo.get_missing_ipinfo(ip, pgrecs['email'][i])
      if record:
         cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(pgrecs['date'][i], pgrecs['time'][i], ip)
         mcnt += PgDBI.pgupdt(table, record, cond)

   s = 's' if cnt > 1 else ''
   PgLOG.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for date {cnd}", PgLOG.LOGWRN)

   return mcnt

def fix_codusage_records(date, cnd):

   table = 'codusage'
   cond = f"date {cnd} AND region IS NULL"
   pgrecs = PgDBI.pgmget(table, 'codidx, email, ip', cond, PgLOG.LGEREX)
   if not pgrecs: return 0
   cnt = len(pgrecs['ip']) if pgrecs else 0
   mcnt = 0
   for i in range(cnt):
      record = PgIPInfo.get_missing_ipinfo(pgrecs['ip'][i], pgrecs['email'][i])
      if record:
         mcnt += PgDBI.pgupdt(table, record, "codidx = '{}'".format(pgrecs['codidx'][i]))

   s = 's' if cnt > 1 else ''
   PgLOG.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for date {cnd}", PgLOG.LOGWRN)

   return mcnt

def fix_wuser_records(date, cnd):

   table = 'wuser'
   cond = f"start_date {cnd} AND region IS NULL"
   pgrecs = PgDBI.pgmget(table, 'wuid, email', cond, PgLOG.LGEREX)
   if not pgrecs: return 0
   cnt = len(pgrecs['wuid']) if pgrecs else 0
   mcnt = 0
   for i in range(cnt):
      email = pgrecs['email'][i]
      record = PgIPInfo.get_missing_ipinfo(None, email)
      if record:
         mcnt += PgDBI.pgupdt(table, record, "wuid = '{}'".format(pgrecs['wuid'][i]))

   s = 's' if cnt > 1 else ''
   PgLOG.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for start_date {cnd}", PgLOG.LOGWRN)

   return mcnt

def fix_ipinfo_records(date, cnd):

   table = 'ipinfo'
   cond = f"adddate {cnd} AND stat_flag = 'M'"
   pgrecs = PgDBI.pgmget(table, 'ip', cond, PgLOG.LGEREX)
   if not pgrecs: return 0
   cnt = len(pgrecs['ip']) if pgrecs else 0
   mcnt = 0
   for i in range(cnt):
      if PgIPInfo.set_ipinfo(pgrecs['ip'][i]): mcnt +=1

   s = 's' if cnt > 1 else ''
   PgLOG.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for adddate {cnd}", PgLOG.LOGWRN)

   return mcnt

#
# call main() to start program
#
if __name__ == "__main__": main()
