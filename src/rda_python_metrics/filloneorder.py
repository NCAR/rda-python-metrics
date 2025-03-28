#!/usr/bin/env python3
#
###############################################################################
#
#     Title : filloneorder
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/10/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to fill one order usage on command line
#
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
###############################################################################
#
import sys
import re
from rda_python_common import PgLOG
from rda_python_common import PgDBI
from rda_python_common import PgIMMA
from rda_python_common import PgUtil

# -t dsid, -e email, -v request data volume, -i data input volume,
# -m delivery method, -a amount charged, -p pay method, -d request date, -x close date,
# -y close time, -c file count, -s specialist login name, -o order id, 
# mandatory options: -t, -e, -v, and -m

#
# main function to run this program
#
def main():

   option = None
   params = {}
   argv = sys.argv[1:]

   for arg in argv:
      ms = re.match(r'^-(\w)$', arg)
      if ms:
         option = ms.group(1)
         if option == "b":
            PgLOG.PGLOG['BCKGRND'] = 1
            option = None
         elif option not in "acdeimopstvx":
            PgLOG.pglog("-{}: Invalid Option".format(option), PgLOG.LGWNEX)
      elif option and option not in params:
         if option == 't': arg = PgUtil.format_dataset_id(arg)
         params[option] = arg
         option = None
      else:
         PgLOG.pglog(arg + ": parameter passed in without leading option", PgLOG.LGWNEX)

   if not params: PgLOG.show_usage('filloneorder')
   PgDBI.dssdb_dbname()
   PgLOG.cmdlog("filloneorder {}".format(' '.join(argv)))

   check_inputs(params)
   add_one_order(params)

   sys.exit(0)

def add_one_order(params):

   year = None
   record = {}
   
   record['dsid'] = params['t']
   record['wuid_request'] = params['u']
   record['dss_uname'] = params['s']
   record['date_request'] = params['d']
   record['date_closed'] = params['x']
   record['method'] = params['m']
   record['size_request'] = params['v']
   record['size_input'] = params['i']
   if 'a' in params: record['amount'] = params['a']
   if 'p' in params: record['pay_method'] = params['p']
   record['count'] = params['c'] if 'c' in params else 0
   if 'o' in params: record['order_number'] = params['o']
   ms = re.match(r'(\d+)-(\d+)-', record['date_request'])
   if ms:
      year = int(ms.group(1))
      record['quarter'] = 1 + int((int(ms.group(2)) - 1) / 3)

   if add_to_allusage(record, year, params['y']) and PgDBI.pgadd("ousage", record, PgLOG.LGEREX):
      PgLOG.pglog("1 order added for " + params['e'], PgLOG.LOGWRN)
   else:
      PgLOG.pglog("No order added for " + params['e'], PgLOG.LOGWRN)

def add_to_allusage(record, year, ctime):

   pgrec = PgDBI.pgget("wuser",  "email, org_type, country",
                       "wuid = {}".format(record['wuid_request']), PgLOG.LGWNEX)
   if pgrec:
      pgrec['dsid'] = record['dsid']
      if pgrec['org_type'] == "UCAR": pgrec['org_type'] = "NCAR"
      pgrec['date'] = record['date_request']
      pgrec['time'] = ctime
      pgrec['quarter'] = record['quarter']
      pgrec['size'] = record['size_request']
      pgrec['method'] = record['method']
      pgrec['source'] = 'O'
      return PgDBI.add_yearly_allusage(year, pgrec)
      
   return 0

#
# check option inputs and fill up the missing ones for default values
#
def check_inputs(params):

   # mandatory inputs
   if 't' not in params:
      PgLOG.pglog("Missing Dataset ID per option -t", PgLOG.LGEREX)

   if not PgDBI.pgget("dataset", '', "dsid = '{}'".format(params['t']), PgLOG.LGEREX):
      PgLOG.pglog(params['t'] + ": dsid not in RDADB", PgLOG.LGEREX)

   if 'v' not in params:
      PgLOG.pglog("Missing order data value in Bytes per option -v", PgLOG.LGEREX)

   if 'm' not in params:
      PgLOG.pglog("Missing data delivery method per option -m", PgLOG.LGEREX)

   if 'e' not in params:
      PgLOG.pglog("Missing user email per option -e", PgLOG.LGEREX)

   (cdate, ctime) = PgUtil.get_date_time()
   # set default values
   if 'i' not in params: params['i'] = params['v']
   if 'x' not in params: params['x'] = cdate
   if 'y' not in params: params['y'] = ctime
   if 'd' not in params: params['d'] = params['x']

   params['u'] = PgDBI.check_wuser_wuid(params['e'], params['d'])
   params['s'] = check_specialist(params['t'], (params['s'] if 's' in params else PgLOG.PGLOG['CURUID']))

   # check if order is recorded already
   ocond = "dsid = '{}' AND wuid_request = {} AND size_request = {} and date_request = '{}'".format(params['t'], params['u'], params['v'], params['d'])
   if PgDBI.pgget("ousage", '', ocond, PgLOG.LGEREX):
      PgLOG.pglog("Order of {} Bytes Data from {} for {} on {} recorded on {} already".format(params['v'], params['t'], params['e'], params['d'], params['x']), PgLOG.LGWNEX)

#
# return the dataset owner if specialist not given
#
def check_specialist(dsid, specialist):

   if specialist and PgDBI.pgget("dssgrp", "", "logname = 'specialist'", PgLOG.LGEREX): return specialist
   scond = "specialist = logname AND dsid = '{}' AND priority = 1".format(dsid)
   pgrec = PgDBI.pgget("dsowner, dssgrp", "specialist", scond, PgLOG.LGEREX)
   return pgrec['specialist'] if pgrec else "datahelp"

#
# call main() to start program
#
if __name__ == "__main__": main()
