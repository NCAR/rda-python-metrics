#!/usr/bin/env python3
###############################################################################
#     Title : filluser
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 02/15/2024
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python functions to retrieve info from Oracle database and fill
#             table user in PostgreSQL database.schema rdadb.dssdb.
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import sys
import re
import time
from os import path as op
from rda_python_common.pg_util import PgUtil

class FillUser(PgUtil):

   def __init__(self):
      super().__init__()
      self.TBNAME = 'dssdb.user'
      self.userno = self.logname = None
      self.missed = False

   # function to read parameters
   def read_parameters(self):
      argv = sys.argv[1:]
      option = None
      for arg in argv:
         if arg == "-b":
            self.PGLOG['BCKGRND'] = 1
         elif re.match(r'^-[inu]$', arg):
            option = arg[1]
            if option == 'i':
               self.missed = True
               option = None
         elif arg[0] == '-':
            self.pglog(arg + ": Invalid Option", self.LGWNEX)
         elif option == "n":
            self.userno = arg
            option = None
         elif option == "u":
            self.logname = arg
            option = None
         else:
            self.pglog(arg + ": Invalid Parameter", self.LGWNEX)
      if not (self.missed or self.userno or self.logname): self.show_usage('filluser')
      if not self.valid_command("pgperson"):
         errmsg = self.PGLOG['SYSERR'] if self.PGLOG['SYSERR'] else "Cannot find command"
         self.pglog("filluser: Cannot be executed on '{}'\n{}".format(self.PGLOG['HOSTNAME'], errmsg), self.LGWNEX)
      self.cmdlog("filluser {}".format(' '.join(argv)))

   # function to start actions
   def start_actions(self):
      self.dssdb_scname()
      if self.missed: # checking and fill missed ones in user table
         self.fill_missed_users()
      else:
         self.fill_one_user()

   # update users with missed info in table dssdb.user
   def fill_missed_users(self):
      self.pglog("Getting incomplete user info", self.LOGWRN)
      pgusers = self.pgmget(self.TBNAME, "*", "stat_flag = 'M'", self.LOGWRN)
      cntall = len(pgusers['logname']) if pgusers else 0
      s = 's' if cntall > 1 else ''
      self.pglog("{} record{} retrieved at {}".format(cntall, s, self.current_datetime()), self.LOGWRN)
      if not cntall: return
      modcnt = 0
      for i in range(cntall):
         pgrec = self.onerecord(pgusers, i)
         record = self.ucar_user_info(pgrec['userno'], pgrec['logname'])
         if record:
            modcnt += self.pgupdt(self.TBNAME, record, "uid = {}".format(pgrec['uid']), self.LOGWRN)
         if (i%500) == 499:
            self.pglog("{}/{} Records modifiled/processed".format(modcnt, (i+1)), self.WARNLG)
      s = 's' if modcnt > 1 else ''
      self.pglog("{} User Record{} modified".format(modcnt, s), self.LOGWRN)
      return modcnt

   # Fill one user for given condition userno or logname
   def fill_one_user(self):
      if self.userno:
         msg = "User ID {}: ".format(self.userno)
      else:
         msg = "User Login Name {}: ".format(self.logname)
      newrec = self.ucar_user_info(self.userno, self.logname)
      if not newrec:
         self.pglog(msg + "No User info found from People DB", self.LOGWRN)
         return
      cond = 'userno = {}'.format(self.userno) if self.userno else  "logname = '{}'".format(self.logname)
      pgrec = self.pgget(self.TBNAME, "*", cond + " AND until_date is null", self.LGWNEX)
      record = self.get_user_record(newrec, pgrec, (newrec['stat_flag'] == 'A'))
      if record == None:
         self.pglog(msg + "User record saved already", self.LOGWRN)
         return
      if record:
         if pgrec:
            if self.pgupdt(self.TBNAME, record, "uid = {}".format(pgrec['uid']), self.LOGWRN):
               self.pglog(msg + "Existing User record Modified", self.LOGWRN)
         else:
            if self.pgadd(self.TBNAME, record, self.LGWNEX):
               self.pglog(msg + "New user record added", self.LOGWRN)
      else:
         record = {'stat_flag' : 'C'}
         record['until_date'] = self.adddate(newrec['start_date'], 0, 0, -1)
         if self.pgupdt(self.TBNAME, record, "uid = {}".format(pgrec['uid']), self.LOGWRN):
            self.pglog(msg + "Existing User record Closed", self.LOGWRN)
         record = self.get_user_record(newrec)
         if record and self.pgadd(self.TBNAME, record, self.LGWNEX):
            self.pglog(msg + "Additional New user record added", self.LOGWRN)

   # local function: get_user_record(orarec: refer to oracle hush record 
   #                                 pgrecs: refer to exist, mysql hush records)
   #         return: a reference to a new mysql record for update or add
   def get_user_record(self, orarec, pgrec = None, neworg = False):
      if not orarec['email']: return None
      ms = re.match(r"^(.+@).+\.ucar\.edu$", orarec['email'], re.I)
      if ms: orarec['email'] = ms.group(1) + "ucar.edu"
      newrec = {}   
      if pgrec:
         if neworg and self.diffdate(orarec['start_date'], pgrec['start_date']) <= 0:
            neworg = False
         if not pgrec['division'] or pgrec['division'] != orarec['division']:
            if neworg and orarec['org_type'] == 'NCAR': return 0
            newrec['division'] = orarec['division']
         if orarec['org_name'] and (not pgrec['org_name'] or pgrec['org_name'] != orarec['org_name']):
            if neworg: return 0
            newrec['org_name'] = orarec['org_name']
         if orarec['country'] and (not pgrec['country'] or orarec['country'] and pgrec['country'] != orarec['country']):
            orarec['country'] = self.set_country_code(orarec)
            if not pgrec['country'] or pgrec['country'] != orarec['country']:
               if neworg: return 0
               newrec['country'] = orarec['country']
         if not pgrec['org_type'] or (orarec['org_type'] and pgrec['org_type'] != orarec['org_type']):
            orarec['org_type'] = self.get_org_type(orarec['org_type'], orarec['email'])
            if not pgrec['org_type'] or pgrec['org_type'] != orarec['org_type']:
               if neworg: return 0
               newrec['org_type'] = orarec['org_type']
         if not pgrec['email'] or pgrec['email'] != orarec['email']:
            if neworg: return 0
            newrec['email'] = orarec['email']
         if not pgrec['ucaremail'] or pgrec['ucaremail'] != orarec['ucaremail']:
            newrec['ucaremail'] = orarec['ucaremail']
         if 'until_date' in orarec and self.diffdate(pgrec['until_date'], orarec['until_date']):
            newrec['until_date'] = orarec['until_date']
         if not pgrec['userno'] or pgrec['userno'] != orarec['userno']:
            newrec['userno'] = orarec['userno']
         if not pgrec['upid'] or pgrec['upid'] != orarec['upid']:
            newrec['upid'] = orarec['upid']
         if not pgrec['logname'] or pgrec['logname'] != orarec['logname']:
            newrec['logname'] = orarec['logname']
         if orarec['lstname'] and (not pgrec['lstname'] or pgrec['lstname'] != orarec['lstname']):
            newrec['lstname'] = orarec['lstname']
         if orarec['fstname'] and (not pgrec['fstname'] or pgrec['fstname'] != orarec['fstname']):
            newrec['fstname'] = orarec['fstname']
         if pgrec['stat_flag'] != orarec['stat_flag']:
            newrec['stat_flag'] = orarec['stat_flag']
         if 'phoneno' in orarec and orarec['phoneno'] and (not pgrec['phoneno'] or pgrec['phoneno'] != orarec['phoneno']):
            newrec['phoneno'] = orarec['phoneno']
         if 'faxno' in orarec and orarec['faxno'] and (not pgrec['faxno'] or pgrec['faxno'] != orarec['faxno']):
            newrec['faxno'] = orarec['faxno']
         if orarec['start_date'] and (not pgrec['start_date'] or self.diffdate(pgrec['start_date'], orarec['start_date']) > 0):
            newrec['start_date'] = orarec['start_date']      
      elif orarec['stat_flag'] == 'A':
         newrec['upid'] = orarec['upid']
         newrec['userno'] = orarec['userno']
         newrec['logname'] = orarec['logname']
         newrec['lstname'] = orarec['lstname']
         newrec['fstname'] = orarec['fstname']
         newrec['stat_flag'] = orarec['stat_flag']
         if orarec['start_date']: newrec['start_date'] = orarec['start_date']
         if 'until_date' in orarec: newrec['until_date'] = orarec['until_date']
         newrec['division'] = orarec['division']
         newrec['org_name'] = orarec['org_name']
         newrec['org_type'] = self.get_org_type(orarec['org_type'], orarec['email'])
         newrec['country'] = self.set_country_code(orarec['email'], orarec['country'])
         newrec['email'] = orarec['email']
         newrec['ucaremail'] = orarec['ucaremail']
         if 'phoneno' in orarec: newrec['phoneno'] = orarec['phoneno']
         if 'faxno' in orarec: newrec['faxno'] = orarec['faxno']
      return newrec if newrec else None

# main function to excecute this script
def main():
   object = FillUser()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
