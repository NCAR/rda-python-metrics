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

   """Retrieve IP geolocation info and fill table ipinfo in PostgreSQL database rdadb."""

   def __init__(self):
      super().__init__()
      # the define options for gathering ipinfo data
      self.DATES = 0x01  # fix data usages for given dates
      self.MONTH = 0x02  # fix data usages for given months
      self.YEARS = 0x04  # fix data usages for given years
      self.NDAYS = 0x08  # fix data usages in recent number of days
      self.MULTI = (self.DATES|self.MONTH|self.YEARS)
      self.SINGL = (self.NDAYS)
      # osdfusage and awsusage carry the same ipinfo fields as tdsusage and were
      # missing here, so nothing could put right what an older version wrote in them
      self.IPINFO['USGTBL'] = ['ipinfo', 'wuser', 'allusage', 'codusage',
                               'tdsusage', 'osdfusage', 'awsusage']
      # the usage tables keyed by date, time and ip rather than by a serial index
      self.DTITBL = ['tdsusage', 'osdfusage', 'awsusage']
      self.IPINFO['CDATE'] = self.curdate()
      self.inputs = []  # array of input values
      self.table = None
      self.option = 0
      self.refresh = 0   # -f: reach records an older version filled in, not just empty ones

   def read_parameters(self):
      """Function to read parameters."""
      argv = sys.argv[1:]
      topt = 0
      for arg in argv:
         if arg == "-b":
            self.PGLOG['BCKGRND'] = 1
         elif arg == "-f":
            self.refresh = 1
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

   def start_actions(self):
      """Function to start actions."""
      self.dssdb_dbname()
      self.fill_ip_info()

   def fill_ip_info(self):
      """Fill ip info in table dssdb.tdsusage."""
      cntall = 0
      # the three date/time/ip keyed tables differ only in their name, so one
      # function serves them and the others keep one apiece
      func = getattr(self, "fix_{}_records".format(
                     'date_time_ip' if self.table in self.DTITBL else self.table))
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

   def get_next_date(self, date, edate):
      """Get next available date."""
      if date < edate:
         ndate = self.enddate(date, 0, 'M')
         if ndate < edate: edate = ndate
      if date < edate:
         cond = f"BETWEEN '{date}' AND '{edate}'"
      else:
         cond = f"= '{date}'"
      return (edate, cond)

   def fix_allusage_records(self, date, cnd):
      """Fix ipinfo in table allusage."""
      cnt = 0
      ms = re.match(r'^(\d+)-', date)
      year = ms.group(1)
      table = 'allusage_' + year
      cond = self.get_usage_condition('date', cnd)
      pgrecs = self.pgmget(table, 'aidx, email, ip', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['ip']) if pgrecs else 0
      mcnt = 0
      self.preset_ip_hostnames(pgrecs['ip'], True)
      for i in range(cnt):
         self.report_progress(table, i, cnt, mcnt)
         record = self.get_missing_ipinfo(pgrecs['ip'][i], pgrecs['email'][i], False, self.refresh)
         if record: mcnt += self.pgupdt(table, record, "aidx = '{}'".format(pgrecs['aidx'][i]))
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for date {cnd}", self.LOGWRN)
      return mcnt

   def get_usage_condition(self, datefld, cnd):
      """The condition selecting the usage records to re-derive the ip info for.

      Without -f only the records left with no region at all are taken, as before.
      With it, the ones an older version did fill in but got wrong are taken too: a
      record whose org_type is '-' had no host name to derive one from, and one
      with no country was never placed.
      """
      if not self.refresh: return f"{datefld} {cnd} AND region IS NULL"
      return (f"{datefld} {cnd} AND (region IS NULL OR country IS NULL"
              " OR org_type IS NULL OR org_type = '-')")

   def report_progress(self, table, procnt, allcnt, mcnt):
      """Say how far along a pass is, a backfill being long enough to look stuck."""
      if procnt%2000 == 0:
         self.pglog("{}: {}/{} record(s) processed/updated".format(table, procnt, mcnt), self.WARNLG)

   def fix_date_time_ip_records(self, date, cnd):
      """Fix ipinfo in a usage table keyed by date, time and ip."""
      table = self.table
      cond = self.get_usage_condition('date', cnd)
      pgrecs = self.pgmget(table, 'date, time, email, ip', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['ip']) if pgrecs else 0
      mcnt = 0
      self.preset_ip_hostnames(pgrecs['ip'], True)
      for i in range(cnt):
         self.report_progress(table, i, cnt, mcnt)
         ip = pgrecs['ip'][i]
         record = self.get_missing_ipinfo(ip, pgrecs['email'][i], False, self.refresh)
         if record:
            cond = "date = '{}' AND time = '{}' AND ip = '{}'".format(pgrecs['date'][i], pgrecs['time'][i], ip)
            mcnt += self.pgupdt(table, record, cond)
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for date {cnd}", self.LOGWRN)
      return mcnt
   
   def fix_codusage_records(self, date, cnd):
      """Fix ipinfo in table codusage."""
      table = 'codusage'
      cond = self.get_usage_condition('date', cnd)
      pgrecs = self.pgmget(table, 'codidx, email, ip', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['ip']) if pgrecs else 0
      mcnt = 0
      self.preset_ip_hostnames(pgrecs['ip'], True)
      for i in range(cnt):
         self.report_progress(table, i, cnt, mcnt)
         record = self.get_missing_ipinfo(pgrecs['ip'][i], pgrecs['email'][i], False, self.refresh)
         if record:
            mcnt += self.pgupdt(table, record, "codidx = '{}'".format(pgrecs['codidx'][i]))
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for date {cnd}", self.LOGWRN)
      return mcnt

   def fix_wuser_records(self, date, cnd):
      """Fix ipinfo in table wuser."""
      table = 'wuser'
      cond = self.get_usage_condition('start_date', cnd)
      pgrecs = self.pgmget(table, 'wuid, email', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['wuid']) if pgrecs else 0
      mcnt = 0
      for i in range(cnt):
         self.report_progress(table, i, cnt, mcnt)
         email = pgrecs['email'][i]
         record = self.get_missing_ipinfo(None, email, False, self.refresh)
         if record:
            mcnt += self.pgupdt(table, record, "wuid = '{}'".format(pgrecs['wuid'][i]))
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for start_date {cnd}", self.LOGWRN)
      return mcnt
   
   def fix_ipinfo_records(self, date, cnd):
      """Fix ip info for table ipinfo.

      Run this before the usage tables. They copy country, region and org_type from
      here, so correcting them against an ipinfo record that is itself still wrong
      just writes the same wrong values back.

      Without -f only the records marked incomplete are taken, as before. With it,
      the ones an older version wrote as complete are taken too: a record carrying
      no org_name never had an answer from ipinfo, that being the only thing which
      supplies it, and one whose host name is still the bare address never had a
      reverse lookup succeed either.
      """
      table = 'ipinfo'
      if self.refresh:
         cond = f"adddate {cnd} AND (stat_flag = 'M' OR org_name IS NULL OR hostname = ip)"
      else:
         cond = f"adddate {cnd} AND stat_flag = 'M'"
      pgrecs = self.pgmget(table, 'ip', cond, self.LGEREX)
      if not pgrecs: return 0
      cnt = len(pgrecs['ip']) if pgrecs else 0
      mcnt = 0
      # every address here is on file by definition, so the prefetch has to be told
      # to resolve them anyway or it finds nothing to do and each lookup goes serial
      self.preset_ip_hostnames(pgrecs['ip'], True)
      for i in range(cnt):
         self.report_progress(table, i, cnt, mcnt)
         if self.set_ipinfo(pgrecs['ip'][i], True, self.refresh): mcnt +=1
      s = 's' if cnt > 1 else ''
      self.pglog(f"{table}: {mcnt} of {cnt} record{s} updated for adddate {cnd}", self.LOGWRN)
      return mcnt

# main function to execute this script
def main():
   object = FillIPInfo()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
