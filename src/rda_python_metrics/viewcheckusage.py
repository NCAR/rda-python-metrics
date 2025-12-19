#!/usr/bin/env python3
###############################################################################
#     Title : viewcheckusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/15/2022
#             2025-03-27 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-19 convert to class ViewCheckUsage
#   Purpose : python program to view historical information of command activities
#             controlled by utility prgoram dscheck.
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import os
import re
import sys
from .pg_view import PgView

class ViewCheckUsage(PgView):

   def __init__(self):
      super().__init__()
      self.VUSG = {
         'SNMS' : "ABCDEFGHIJKLMNPQRSTUVWZ",   # all available short field names in %FLDS
         'OPTS' : 'aABcCdDhHilLmnOqrsStTwyz',  # all available options, used for %params
         'NOPT' : 'abwz',                      # stand alone option without inputs
         'ACND' : 'cdhilLmnsSty',              # available array condition options
         'RCND' : 'BDqrT',                     # available range condition options
         'CNDS' : 'aBcdDhilmnqrsStTy',         # condition options, ACND, RCND and 'a'
         'HCND' : '',                          # condition options for having clause
         'ECND' : 'my',                        # condition options need evaluating
         'SFLD' : 'CDHNSTW',                   # string fields, to be quoted in condition
         'UFLD' : 'NW',                        # string fields must be in upper case
         'LFLD' : 'ST',                        # string fields must be in lower case
      }
      # keys %FLDS - short field names
      # column 0   - column title showing in usage view
      # column 1   - field name in format as shown in select clauses
      # column 2   - field name shown in where condition query string
      # column 3   - table name that the field belongs to 
      # column 4   - output field length, the longer one of data size and comlun title, determine
      #              dynamically if it is 0. Negative values indicate right justification
      # column 5   - precision for floating point value if positive and show total value if not zero
      # column 6   - field flag to indicate it is a group, distinct or sum field
      self.FLDS = {
      # SHRTNM COLUMNNANE      FIELDNAME                         CNDNAME        TBLNAM       Size Prc Grp/Sum
         'A' : ['ARGV',         "argv",                           'argv',        'dschkhist',  0,  0,  'G'],
         'C' : ['COMMAND',      "command",                        'command',     'dschkhist',  0,  0,  'G'],
         'D' : ['DATE',         "date",                           'date',        'dschkhist', 10,  0,  'G'],
         'E' : ['ERRMSG',       "errmsg",                         'errmsg',      'dschkhist',  0,  0,  'G'],
         'H' : ['HOSTNAME',     "hostname",                       'hostname',    'dschkhist',  0,  0,  'G'],
         'I' : ['CHKIDX',       "cindex",                         'cindex',      'dschkhist',  0,  0,  'G'],
         'K' : ['TIME',         "time",                           'time',        'dschkhist',  8,  0,  'G'],
         'L' : ['BATCHID',      "bid",                            'bid',         'dschkhist',  0,  0,  'G'],
         'M' : ['MONTH',        self.fmtym("date"),              'date',        'dschkhist',  7,  0,  'G'],
         'G' : ['TRIED',        "tcount",                         'tcount',      'dschkhist',  0,  0,  'G'],
         'P' : ['DATAPROC',     "size",                           'size',        'dschkhist', -14, -1, 'G'],
         'Q' : ['QUETIME',      "quetime",                        'quetime',     'dschkhist',  0,  0,  'G'],
         'R' : ['RUNTIME',      "ttltime",                        'ttltime',     'dschkhist',  0,  0,  'G'],
         'S' : ['SPECIALIST',   "specialist",                     'specialist',  'dschkhist',  9,  0,  'G'],
         'T' : ['DATASET',      "dsid",                           'dsid',        'dschkhist',  0,  0,  'G'],
         'N' : ['AN',           "action",                         'action',      'dschkhist',  2,  0,  'G'],
         'W' : ['STATUS',       "status",                         'status',      'dschkhist',  5,  0,  'G'],
         'Y' : ['YEAR',         self.fmtyr("date"),              'date',        'dschkhist',  4,  0,  'G'],
         'B' : ['MBYTESDATA',   "round(sum(size)/1000000, 4)",    'B',           'dschkhist', -14, 3,  'S'],
         'U' : ['HREXEC',       "round(sum(ttltime)/3600, 3)",    'U',           'dschkhist', -7,  2,  'S'],
         'V' : ['HRQUEUE',      "round(sum(quetime)/3600, 3)",    'V',           'dschkhist', -7,  2,  'S'],
         'J' : ['#FILEPROC',    "count(dcount)",                  'J',           'dschkhist', -9, -1,  'S'],
         'F' : ['FILECOUNT',    "count(fcount)",                  'F',           'dschkhist', -9, -1,  'S'],
         'Z' : ['#CHECKS',      "count(cindex)",                  'Z',           'dschkhist', -8, -1,  'S'],
         'X' : ['INDEX',        "",                               'X',           '',          -6,  0,  ' ']
      }
      # keys %EXPAND - short field names allow zero usage
      # column 0   - expand ID for group of fields
      # column 1   - field name shown in where condition query string
      # column 2   - field name in format as shown in select clauses
      # column 3   - table name that the field belongs to 
      self.EXPAND = {
      # SHRTNM EXPID     CNDSTR    FIELDNAME       TBLNAM
         'D' : ["TIME",   "dDmy"],
         'M' : ["TIME",   "dDmy"],
         'Y' : ["TIME",   "dDmy"],
         'C' : ["CHECK",  "csS",     "command",     "dschkhist"],
         'S' : ["CHECK",  "csS",     "status",      "dschkhist"],
         'W' : ["CHECK",  "csS",     "specialist",  "dschkhist"],
      }
      # valid options for %params, a hash array of command line parameters
      #   a -- 1 to view all usage info available
      #   A -- number or records to return
      #   b -- array of batch ids
      #   B -- batch id range range, array of 1 or 2 batch ids
      #   c -- array of specified commands
      #   C -- a string of short field names for viewing usages
      #   d -- array of specified dates 
      #   D -- dates range, array of 1 or 2 dates in format of YYYY-MM-DD
      #   h -- array of specified hostnames
      #   H -- a string of report title to replace the default one
      #   i -- array of check indices
      #   L -- column delimiter for output
      #   m -- array of specified months
      #   n -- array of specified action names
      #   O -- a string of short field names for sorting on
      #   q -- queued time range, array of 1 or 2 queued time in seconds
      #   r -- run time range, array of 1 or 2 run time in seconds
      #   s -- array of specified status
      #   S -- array of login names of specialists who own the requests
      #   t -- array of specified dataset names
      #   T -- dataset range, array of 1 or 2 dataset names
      #   w -- generate view without totals
      #   y -- array of specified years
      #   z -- generate view including entries with zero usage
      self.params = {}
      # relationship between parameter options and short field names, A option is not
      # related to a field name if it is not in keys %SNS 
      self.SNS = {
         'b' : 'L', 'B' : 'L', 'c' : 'C', 'd' : 'D', 'D' : 'D', 'h' : 'H', 'i' : 'I', 'm' : 'M', 'n' : 'N',
         'q' : 'Q', 'r' : 'R', 'q' : 'Q', 's' : 'W', 'S' : 'S', 't' : 'T', 'T' : 'T', 'y' : 'Y'
      }
      self.tablenames = self.fieldnames = self.condition = ''
      self.sfields = []
      self.gfields = []
      self.dfields = []
      self.pgname = 'viewcheckusage'

   # function to read parameters
   def read_parameters(self):
      self.view_dbinfo()
      argv = sys.argv[1:]
      inputs = []
      option = 'C'
      for arg in argv:
         if re.match(r'^-.*$', arg):
            curopt = arg[1:2]
            if curopt and self.VUSG['OPTS'].find(curopt) > -1:
               if self.VUSG['NOPT'].find(option) > -1:
                  self.params[option] = 1
               elif inputs:
                  self.params[option]= inputs   # record input array
                  inputs = []      # empty input array
               option = curopt     # start a new option
            else:
               self.pglog(arg + ": Unknown Option", self.LGWNEX)
         else:
            val = arg
            if val != '!' and option in self.SNS:
               sfld = self.SNS[option]
               if self.VUSG['SFLD'].find(sfld) > -1:
                  if self.VUSG['UFLD'].find(sfld) > -1:
                     val = arg.upper()     # in case not in upper case
                  elif self.VUSG['LFLD'].find(sfld) > -1:
                     val = arg.lower()     # in case not in lower case
                  if option == 'c':
                     val = self.get_country_name(val)
                  elif option == 't' or option == 'T':
                     val = self.format_dataset_id(val)   # add 'ds' if only numbers
                  val = "'{}'".format(val)
            inputs.append(val)
      # record the last option
      if self.VUSG['NOPT'].find(option) > -1:
         self.params[option] = 1
      elif inputs:
         self.params[option] = inputs   # record input array
      if not self.params:
         self.show_usage(self.pgname)
      else:
         self.check_enough_options()

   # function to start actions
   def start_actions(self):
      usgtable = 'dschkhist'
      self.build_query_strings(usgtable)   # build tablenames, fieldnames, and condtions
      records = self.pgmget(self.tablenames, self.fieldnames, self.condition, self.UCLWEX)
      if not records: self.pglog("No Usage Found For Given Conditions", self.LGWNEX)
      totals = None if 'w' in self.params else {}
      if self.dfields or totals != None:
         records = self.compact_hash_groups(records, self.gfields, self.sfields, self.dfields, totals)
      if 'z' in self.params: records = self.expand_records(records)
      ostr = self.params['O'][0] if 'O' in self.params else self.params['C'][0]
      records = self.order_records(records, ostr.replace('X', ''))
      self.simple_output(self.params, self.FLDS, records, totals)

   # check if enough information entered on command line for generate view/report, exit if not
   def check_enough_options(self):
      flds = self.params['C'][0] if 'C' in self.params else 'X'
      if flds == 'X': self.pglog("{}: MISS short field names '{}'".format(self.pgname, self.VUSG['SNMS']), self.LGWNEX)
      for sn in flds:
         if sn == 'X': continue  # do not process INDEX field
         if self.VUSG['SNMS'].find(sn) == -1:
            self.pglog("{}: Field sn must be in short field names: {}X".format(self.pgname, self.VUSG['SNMS']), self.LGWNEX)
         if 'z' not in self.params or sn in self.EXPAND: continue
         fld = self.FLDS[sn]
         if fld[6] != 'G': continue
         self.pglog("{}: cannot show zero usage for unexpandable field {} - {}".format(self.pgname, sn, fld[0]), self.LGWNEX)
      for arg in self.params:
         if arg in self.VUSG['CNDS']: return
      self.pglog("{}: miss condition options '{}'".format(self.pgname, self.VUSG['CNDS']), self.LGWNEX)

   # process parameter options to build all query strings
   # global variables are used directly and nothing passes in and returns back
   def build_query_strings(self, usgtable):
      joins = having = ordernames = groupnames = ''
      self.tablenames = usgtable
      cols = self.params['C'][0]
      if 'U' in self.params:    # reset units for file and read sizes
         if cols.find('B') > -1: self.FLDS['B'] = self.set_data_unit(self.FLDS['B'], self.params['U'][0], "sum(size)")
         if cols.find('P') > -1: self.FLDS['P'] = self.set_data_unit(self.FLDS['P'], self.params['U'][0], "size")
      for opt in self.params:
         if opt == 'O' or self.VUSG['NOPT'].find(opt) > -1: continue
         if opt == 'C':   # build field, table and group names
            for sn in cols:
               if sn == 'X': continue  # do not process INDEX field
               fld = self.FLDS[sn]
               if self.fieldnames: self.fieldnames += ', '
               self.fieldnames += "{} {}".format(fld[1], sn)   # add to field name string
               (self.tablenames, joins) = self.join_query_tables(fld[3], self.tablenames, joins, usgtable)
               if fld[6] == 'S':
                  self.sfields.append(sn)
               else:
                  if groupnames: groupnames += ', '
                  groupnames += sn     # add to group name string
                  if fld[6] == 'D':
                     self.dfields.append(sn)
                  else:
                     self.gfields.append(sn)
         elif opt == 'O':
            continue   # order records later
         elif self.VUSG['CNDS'].find(opt) > -1:
            sn = self.SNS[opt]
            fld = self.FLDS[sn]
            # build having and where conditon strings
            cnd = self.get_view_condition(opt, sn, fld, self.params, self.VUSG)
            if cnd:
               if self.VUSG['HCND'].find(opt) > -1:
                  if having: having += ' AND '
                  having += cnd
               else:
                  if self.condition: self.condition += ' AND '
                  self.condition += cnd
               (self.tablenames, joins) = self.join_query_tables(fld[3], self.tablenames, joins, usgtable)
      # append joins, group by, order by, and having strings to condition string
      if joins:
         if self.condition:
            self.condition = "{} AND {}".format(joins, self.condition)
         else:
            self.condition = joins
      if groupnames and self.sfields: self.condition += " GROUP BY " + groupnames
      if having: self.condition += " HAVING " + having

   # exand records as needed
   def expand_records(self, records):
      recs = self.expand_query("TIME", records, self.params, self.EXPAND)
      trecs = self.expand_query("CHECK", records, self.params, self.EXPAND, self.VUSG, self.SNS, self.FLDS)
      recs = self.crosshash(recs, trecs)
      return self.joinhash(records, recs, 0, 1)

# main function to excecute this script
def main():
   object = ViewCheckUsage()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
