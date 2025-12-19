#!/usr/bin/env python3
###############################################################################
#     Title : fillipinfo
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 08/26/2023
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-17 convert to FillIPInfo
#   Purpose : python program to retrieve ip info and  
#             and fill table ipinfo
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import sys
import re
from .pg_ipinfo import PgIPInfo

class FillIPInfo(PgIPInfo):

   def __init__(self):
      super()._init__()
      # the define options for gathering ipinfo data
      self.DATES = 0x01  # fix data usages for given dates
      self.MONTH = 0x02  # fix data usages for given months
      self.YEARS = 0x04  # fix data usages for given years
      self.NDAYS = 0x08  # fix data usages in recent number of days
      self.MULTI = (self.DATES|self.MONTH|self.YEARS)
      self.SINGL = (self.NDAYS)
      self.IPINFO = {
         'USGTBL'  : ['ipinfo', 'wuser', 'allusage', 'codusage', 'tdsusage'],
         'CDATE' : self.curdate(),
      }
      self.inputs = []  # array of input values
      self.table = None  # table names: ipinfo, allusage, globususage, or tdsusage
      self.option = 0

   # function to read parameters
   def read_parameters(self):
      argv = sys.argv[1:]
      topt = 0
      for arg in argv:
         if arg == "-b":
            self.PGLOG['BCKGRND'] = 1
         elif re.match(r'^-[dmNy]$', arg) and self.option == 0:
            if arg == "-d":
               self.option = self.DATES
            elif arg == "-m":
               self.option = self.MONTH
            elif arg == "-y":
               self.option = self.YEARS
            elif arg == "-N":
               self.option = self.NDAYS
         elif arg == "-t":
            topt = 1
         elif re.match(r'^-', arg):
            self.pglog(arg + ": Invalid Option", self.LGWNEX)
         elif topt:
            if arg not in self.IPINFO['USGTBL']:
               self.pglog("{}: Invalid Table Name; must be in ({})".format(arg, ','.join(self.IPINFO['USGTBL'])), self.LGWNEX)
            self.table = arg
            topt = 0
         elif self.option&self.MULTI or self.option&self.SINGL and not self.inputs:
            self.inputs.append(arg)
         else:
            self.pglog(arg + ": Invalid Parameter", self.LGWNEX)
      if not (self.inputs and self.table): self.show_usage('fillipinfo')
      self.cmdlog("fillipinfo {}".format(' '.join(argv)))

   # function to start actions
   def start_actions(self):
      self.dssdb_dbname()
      self.fill_ip_info()

   # Fill ip info in table dssdb.tdsusage
   def fill_ip_info(self):
      cntall = 0
      func = getattr(self, f"fix_{self.table}_records")
      for input in self.inputs:
         if self.option&self.NDAYS:
            edate = self.IPINFO['CDATE']
            date = self.adddate(edate, 0, 0, -int(input))
         elif self.option&self.DATES:
            edate = date = input
         elif self.option&self.MONTH:
            tms = input.split('-')
            date = "{}-{:02}-01".format(tms[0], int(tms[1]))
            edate = self.enddate(date, 0, 'M')
         else:
            date = input + "-01-01"
            edate = input + "-12-31"
         while True:
            (ndate, cond) = self.get_next_date(date, edate)
            cntall += func(date, cond)
            if ndate >= edate: break
            date = self.adddate(ndate, 0, 0, 1)
      if cntall > 2:
         self.pglog(f"{self.table}: Total {cntall} records updated", self.LOGWRN)

   # get next available date
   def get_next_date(self, date, edate):
      if date < edate:
         ndate = self.enddate(date, 0, 'M')
         if ndate < edate: edate = ndate
      if date < edate:
         cond = f"BETWEEN '{date}' AND '{edate}'"
      else:
         cond = f"= '{date}'"
      return (edate, cond)

   # fix ipinfo in table allusage
   def fix_allusage_records(self, date, cnd):
      cnt = 0
      ms = re.match(r'^(\d+)-', date)
      year = ms.group(1)
      table = 'allusage_' + year
      cond = f"date {cnd} AND region IS NULL"
      pgrecs = self.pgmget(table, 'aidx, email, ip', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['ip']) if pgrecs else 0
      mcnt = 0
      for i in range(cnt):
         record = self.get_missing_ipinfo(pgrecs['ip'][i], pgrecs['email'][i])
         if record: mcnt += self.pgupdt(table, record, "aidx = '{}'".format(pgrecs['aidx'][i]))
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for date {cnd}", self.LOGWRN)
      return mcnt

   # fix ipinfo in table tdsusage
   def fix_tdsusage_records(self, date, cnd):
      table = 'tdsusage'
      cond = f"date {cnd} AND region IS NULL"
      pgrecs = self.pgmget(table, 'date, time, email, ip', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['ip']) if pgrecs else 0
      mcnt = 0
      for i in range(cnt):
         ip = pgrecs['ip'][i]
         record = self.get_missing_ipinfo(ip, pgrecs['email'][i])
         if record:
            cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(pgrecs['date'][i], pgrecs['time'][i], ip)
            mcnt += self.pgupdt(table, record, cond)
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for date {cnd}", self.LOGWRN)
      return mcnt
   
   # fix ipinfo in table codusage
   def fix_codusage_records(self, date, cnd):
      table = 'codusage'
      cond = f"date {cnd} AND region IS NULL"
      pgrecs = self.pgmget(table, 'codidx, email, ip', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['ip']) if pgrecs else 0
      mcnt = 0
      for i in range(cnt):
         record = self.get_missing_ipinfo(pgrecs['ip'][i], pgrecs['email'][i])
         if record:
            mcnt += self.pgupdt(table, record, "codidx = '{}'".format(pgrecs['codidx'][i]))
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for date {cnd}", self.LOGWRN)
      return mcnt

   # fix ipinfo in table wuser
   def fix_wuser_records(self, date, cnd):
      table = 'wuser'
      cond = f"start_date {cnd} AND region IS NULL"
      pgrecs = self.pgmget(table, 'wuid, email', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['wuid']) if pgrecs else 0
      mcnt = 0
      for i in range(cnt):
         email = pgrecs['email'][i]
         record = self.get_missing_ipinfo(None, email)
         if record:
            mcnt += self.pgupdt(table, record, "wuid = '{}'".format(pgrecs['wuid'][i]))
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for start_date {cnd}", self.LOGWRN)
      return mcnt
   
   # fix ip info for table ipinfo
   def fix_ipinfo_records(self, date, cnd):
      table = 'ipinfo'
      cond = f"adddate {cnd} AND stat_flag = 'M'"
      pgrecs = self.pgmget(table, 'ip', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['ip']) if pgrecs else 0
      mcnt = 0
      for i in range(cnt):
         if self.set_ipinfo(pgrecs['ip'][i]): mcnt +=1
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for adddate {cnd}", self.LOGWRN)
      return mcnt

# main function to excecute this script
def main():
   object = FillIPInfo()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
