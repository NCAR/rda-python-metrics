#!/usr/bin/env python3
###############################################################################
#
#     Title : filloneorder
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/10/2022
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-17 convert to class FillONEOrder
#   Purpose : python program to fill one order usage on command line
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import sys
import re
from rda_python_common.pg_util import PgUtil

# -t dsid, -e email, -v request data volume, -i data input volume,
# -m delivery method, -a amount charged, -p pay method, -d request date, -x close date,
# -y close time, -c file count, -s specialist login name, -o order id,
# mandatory options: -t, -e, -v, and -m
class FillONEOrder(PgUtil):

   def __init__(self):
      super().__init__()
      self.params = {}

   # function to read parameters
   def read_parameters(self):
      option = None
      argv = sys.argv[1:]
      for arg in argv:
         ms = re.match(r'^-(\w)$', arg)
         if ms:
            option = ms.group(1)
            if option == "b":
               self.PGLOG['BCKGRND'] = 1
               option = None
            elif option not in "acdeimopstvx":
               self.pglog("-{}: Invalid Option".format(option), self.LGWNEX)
         elif option and option not in self.params:
            if option == 't': arg = self.format_dataset_id(arg)
            self.params[option] = arg
            option = None
         else:
            self.pglog(arg + ": parameter passed in without leading option", self.LGWNEX)
   
      if not self.params: self.show_usage('filloneorder')
      self.cmdlog("filloneorder {}".format(' '.join(argv)))

   # function to start actions
   def start_actions(self):
      self.dssdb_dbname()
      self.check_inputs()
      self.add_one_order()

   # add one customized order into RDADB
   def add_one_order(self):
      year = None
      record = {}
      record['dsid'] = self.params['t']
      record['wuid_request'] = self.params['u']
      record['dss_uname'] = self.params['s']
      record['date_request'] = self.params['d']
      record['date_closed'] = self.params['x']
      record['method'] = self.params['m']
      record['size_request'] = self.params['v']
      record['size_input'] = self.params['i']
      if 'a' in self.params: record['amount'] = self.params['a']
      if 'p' in self.params: record['pay_method'] = self.params['p']
      record['count'] = self.params['c'] if 'c' in self.params else 0
      if 'o' in self.params: record['order_number'] = self.params['o']
      ms = re.match(r'(\d+)-(\d+)-', record['date_request'])
      if ms:
         year = int(ms.group(1))
         record['quarter'] = 1 + int((int(ms.group(2)) - 1) / 3)
      if self.add_to_allusage(record, year, self.params['y']) and self.pgadd("ousage", record, self.LGEREX):
         self.pglog("1 order added for " + self.params['e'], self.LOGWRN)
      else:
         self.pglog("No order added for " + self.params['e'], self.LOGWRN)

   # add record into table allusage
   def add_to_allusage(self, record, year, ctime):
      pgrec = self.pgget("wuser",  "email, org_type, country, region",
                          "wuid = {}".format(record['wuid_request']), self.LGWNEX)
      if pgrec:
         pgrec['dsid'] = record['dsid']
         if pgrec['org_type'] == "UCAR": pgrec['org_type'] = "NCAR"
         pgrec['date'] = record['date_request']
         pgrec['time'] = ctime
         pgrec['quarter'] = record['quarter']
         pgrec['size'] = record['size_request']
         pgrec['method'] = record['method']
         pgrec['source'] = 'O'
         return self.add_yearly_allusage(year, pgrec)
      return 0

   # check option inputs and fill up the missing ones for default values
   def check_inputs(self):
      # mandatory inputs
      if 't' not in self.params:
         self.pglog("Missing Dataset ID per option -t", self.LGEREX)
      if not self.pgget("dataset", '', "dsid = '{}'".format(self.params['t']), self.LGEREX):
         self.pglog(self.params['t'] + ": dsid not in RDADB", self.LGEREX)
      if 'v' not in self.params:
         self.pglog("Missing order data value in Bytes per option -v", self.LGEREX)
      if 'm' not in self.params:
         self.pglog("Missing data delivery method per option -m", self.LGEREX)
      if 'e' not in self.params:
         self.pglog("Missing user email per option -e", self.LGEREX)
      (cdate, ctime) = self.get_date_time()
      # set default values
      if 'i' not in self.params: self.params['i'] = self.params['v']
      if 'x' not in self.params: self.params['x'] = cdate
      if 'y' not in self.params: self.params['y'] = ctime
      if 'd' not in self.params: self.params['d'] = self.params['x']
      self.params['u'] = self.check_wuser_wuid(self.params['e'], self.params['d'])
      self.params['s'] = self.check_specialist(self.params['t'], (self.params['s'] if 's' in self.params else self.PGLOG['CURUID']))
      # check if order is recorded already
      ocond = "dsid = '{}' AND wuid_request = {} AND size_request = {} and date_request = '{}'".format(self.params['t'], self.params['u'], self.params['v'], self.params['d'])
      if self.pgget("ousage", '', ocond, self.LGEREX):
         self.pglog("Order of {} Bytes Data from {} for {} on {} recorded on {} already".format(self.params['v'], self.params['t'], self.params['e'], self.params['d'], self.params['x']), self.LGWNEX)

   # return the dataset owner if specialist not given
   def check_specialist(self, dsid, specialist):
      if specialist and self.pgget("dssgrp", "", "logname = 'specialist'", self.LGEREX): return specialist
      scond = "specialist = logname AND dsid = '{}' AND priority = 1".format(dsid)
      pgrec = self.pgget("dsowner, dssgrp", "specialist", scond, self.LGEREX)
      return pgrec['specialist'] if pgrec else "datahelp"

# main function to excecute this script
def main():
   object = FillONEOrder()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
