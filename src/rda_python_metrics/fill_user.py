#!/usr/bin/env python3
#
###############################################################################
#
#     Title : filluser
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 02/15/2024
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python functions to retrieve info from Oracle database and fill
#             table user in PostgreSQL database.schema rdadb.dssdb.
#
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
###############################################################################
import sys
import re
import time
from os import path as op
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgDBI

TBNAME = 'dssdb.user'

#
# main function to run this program
#
def main():

   argv = sys.argv[1:]
   missed = False
   userno = logname = option = None

   for arg in argv:
      if arg == "-b":
         PgLOG.PGLOG['BCKGRND'] = 1
      elif re.match(r'^-[inu]$', arg):
         option = arg[1]
         if option == 'i':
            missed = True
            option = None
      elif arg[0] == '-':
         PgLOG.pglog(arg + ": Invalid Option", PgLOG.LGWNEX)
      elif option == "n":
         userno = arg
         option = None
      elif option == "u":
         logname = arg
         option = None
      else:
         PgLOG.pglog(arg + ": Invalid Parameter", PgLOG.LGWNEX)

   if not (missed or userno or logname): PgLOG.show_usage('filluser')

   if not PgLOG.valid_command("pgperson"):
      errmsg = PgLOG.PGLOG['SYSERR'] if PgLOG.PGLOG['SYSERR'] else "Cannot find command"
      PgLOG.pglog("filluser: Cannot be executed on '{}'\n{}".format(PgLOG.PGLOG['HOSTNAME'], errmsg), PgLOG.LGWNEX)

   PgDBI.dssdb_scname()
   PgLOG.cmdlog("filluser {}".format(' '.join(argv)))
   if missed: # checking and fill missed ones in user table
      fill_missed_users()
   else:
      fill_one_user(userno, logname)

   sys.exit(0)

#
# update users with missed info in table dssdb.user
#
def fill_missed_users():

   PgLOG.pglog("Getting incomplete user info", PgLOG.LOGWRN)
   pgusers = PgDBI.pgmget(TBNAME, "*", "stat_flag = 'M'", PgLOG.LOGWRN)
   cntall = len(pgusers['logname']) if pgusers else 0
   s = 's' if cntall > 1 else ''
   PgLOG.pglog("{} record{} retrieved at {}".format(cntall, s, PgLOG.current_datetime()), PgLOG.LOGWRN)
   if not cntall: return
   modcnt = 0
   for i in range(cntall):
      pgrec = PgUtil.onerecord(pgusers, i)
      record = PgDBI.ucar_user_info(pgrec['userno'], pgrec['logname'])
      if record:
         modcnt += PgDBI.pgupdt(TBNAME, record, "uid = {}".format(pgrec['uid']), PgLOG.LOGWRN)
      
      if (i%500) == 499:
         PgLOG.pglog("{}/{} Records modifiled/processed".format(modcnt, (i+1)), PgLOG.WARNLG)
   s = 's' if modcnt > 1 else ''
   PgLOG.pglog("{} User Record{} modified".format(modcnt, s), PgLOG.LOGWRN)
   return modcnt

#
# Fill one user for given condition userno or logname
#
def fill_one_user(userno, logname):

   if userno:
      msg = "User ID {}: ".format(userno)
   else:
      msg = "User Login Name {}: ".format(logname)
   modcnt = cntadd = 0
   newrec = PgDBI.ucar_user_info(userno, logname)
   if not newrec:
      PgLOG.pglog(msg + "No User info found from People DB", PgLOG.LOGWRN)
      return

   cond = 'userno = {}'.format(userno) if userno else  "logname = '{}'".format(logname)
   pgrec = PgDBI.pgget(TBNAME, "*", cond + " AND until_date is null", PgLOG.LGWNEX)
   record = get_user_record(newrec, pgrec, (newrec['stat_flag'] == 'A'))
   if record == None:
      PgLOG.pglog(msg + "User record saved already", PgLOG.LOGWRN)
      return
   if record:
      if pgrec:
         if PgDBI.pgupdt(TBNAME, record, "uid = {}".format(pgrec['uid']), PgLOG.LOGWRN):
            PgLOG.pglog(msg + "Existing User record Modified", PgLOG.LOGWRN)
            modcnt += 1
      else:
         if PgDBI.pgadd(TBNAME, record, PgLOG.LGWNEX):
            PgLOG.pglog(msg + "New user record added", PgLOG.LOGWRN)
            cntadd += 1               
   else:
      record = {'stat_flag' : 'C'}
      record['until_date'] = PgUtil.adddate(newrec['start_date'], 0, 0, -1)
      if PgDBI.pgupdt(TBNAME, record, "uid = {}".format(pgrec['uid']), PgLOG.LOGWRN):
         PgLOG.pglog(msg + "Existing User record Closed", PgLOG.LOGWRN)
         modcnt += 1

      record = get_user_record(newrec)
      if record and PgDBI.pgadd(TBNAME, record, PgLOG.LGWNEX):
         PgLOG.pglog(msg + "Additional New user record added", PgLOG.LOGWRN)
         cntadd += 1

#
# local function: get_user_record(orarec: refer to oracle hush record 
#                                 pgrecs: refer to exist, mysql hush records)

#         return: a reference to a new mysql record for update or add
#
def get_user_record(orarec, pgrec = None, neworg = False):

   if not orarec['email']: return None

   ms = re.match("^(.+\@).+\.ucar\.edu$", orarec['email'], re.I)
   if ms: orarec['email'] = ms.group(1) + "ucar.edu"

   newrec = {}   
   if pgrec:
      if neworg and PgUtil.diffdate(orarec['start_date'], pgrec['start_date']) <= 0:
         neworg = False
      if not pgrec['division'] or pgrec['division'] != orarec['division']:
         if neworg and orarec['org_type'] == 'NCAR': return 0
         newrec['division'] = orarec['division']
      if orarec['org_name'] and (not pgrec['org_name'] or pgrec['org_name'] != orarec['org_name']):
         if neworg: return 0
         newrec['org_name'] = orarec['org_name']
      if orarec['country'] and (not pgrec['country'] or orarec['country'] and pgrec['country'] != orarec['country']):
         orarec['country'] = PgDBI.set_country_code(orarec)
         if not pgrec['country'] or pgrec['country'] != orarec['country']:
            if neworg: return 0
            newrec['country'] = orarec['country']
      if not pgrec['org_type'] or (orarec['org_type'] and pgrec['org_type'] != orarec['org_type']):
         orarec['org_type'] = PgDBI.get_org_type(orarec['org_type'], orarec['email'])
         if not pgrec['org_type'] or pgrec['org_type'] != orarec['org_type']:
            if neworg: return 0
            newrec['org_type'] = orarec['org_type']
      if not pgrec['email'] or pgrec['email'] != orarec['email']:
         if neworg: return 0
         newrec['email'] = orarec['email']
      if not pgrec['ucaremail'] or pgrec['ucaremail'] != orarec['ucaremail']:
         newrec['ucaremail'] = orarec['ucaremail']
      if 'until_date' in orarec and PgUtil.diffdate(pgrec['until_date'], orarec['until_date']):
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
      if orarec['start_date'] and (not pgrec['start_date'] or PgUtil.diffdate(pgrec['start_date'], orarec['start_date']) > 0):
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
      newrec['org_type'] = PgDBI.get_org_type(orarec['org_type'], orarec['email'])
      newrec['country'] = PgDBI.set_country_code(orarec['email'], orarec['country'])
      newrec['email'] = orarec['email']
      newrec['ucaremail'] = orarec['ucaremail']
      if 'phoneno' in orarec: newrec['phoneno'] = orarec['phoneno']
      if 'faxno' in orarec: newrec['faxno'] = orarec['faxno']

   return newrec if newrec else None

#
# call main() to start program
#
if __name__ == "__main__": main()
