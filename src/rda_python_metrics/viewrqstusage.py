#!/usr/bin/env python
###############################################################################
#     Title : viewrqstusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/15/2022
#             2025-03-28 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-19 convert to class ViewRQSTUsage
#   Purpose : python program to view usage information for Web Online files
#             staged by utility prgoram dsrqst.
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import os
import re
import sys
from .pg_view import PgView

class ViewRQSTUsage(PgView):
   
   def __init__(self):
      super().__init__()
      self.VUSG = {
         'SNMS' : "ABCDEFGHIJKLMNOPQRSTUVWYZ",        # all available short field names in FLDS
         'OPTS' : 'AabcCdDeEfFghHiIlLmnMNoOsStTUvwy', # all available options, used for params
         'NOPT' : 'abhnwz',                           # stand alone option without inputs
         'ACND' : 'cdefgilmMosStvy',                  # available array condition options
         'RCND' : 'DFNT',                             # available range condition options
         'CNDS' : 'acdDefFgilmMNosStTvy',             # condition options, ACND, RCND and 'a'
         'HCND' : 'N',                                # condition options for having clause
         'ECND' : 'my',                               # condition options need evaluating
         'SFLD' : 'DEGILNOPSTUW',                     # string fields, to be quoted in condition
         'UFLD' : 'ILNOSW',                           # string fields must be in upper case
         'LFLD' : 'EPT',                              # string fields must be in lower case
      }
      # keys FLDS - short field names
      # column 0   - column title showing in usage view
      # column 1   - field name in format as shown in select clauses
      # column 2   - field name shown in where condition query string
      # column 3   - table name that the field belongs to 
      # column 4   - output field length, the longer one of data size and comlun title, determine
      #              dynamically if it is 0. Negative values indicate right justification
      # column 5   - precision for floating point value if positive and show total value if not zero
      # column 6   - field flag to indicate it is a group, distinct or sum field
      self.FLDS = {
      # SHRTNM COLUMNNANE      FIELDNAME                              CNDNAME          TBLNAM     Size Prc Grp/Sum
         'D' : ['DATE',         "date_rqst",                           'date_rqst',     'dspurge', 10,  0,  'G'],
         'E' : ['EMAIL',        "dspurge.email",                       'dspurge.email', 'dspurge',  0,  0,  'G'],
         'U' : ['FILENAME',     "wfile",                               'wfile',         'wfpurge',  0,  0,  'G'],
         'G' : ['ORGNAME',      "org_name",                            'org_name',      'wuser',    0,  0,  'G'],
         'I' : ['FIRSTNAME',    "fstname",                             'fstname',       'wuser',    0,  0,  'G'],
         'K' : ['TIME',         "time_rqst",                           'time_rqst',     'dspurge',  8,  0,  'G'],
         'L' : ['LASTNAME',     "lstname",                             'lstname',       'wuser',    0,  0,  'G'],
         'M' : ['MONTH',        self.fmtym("date_rqst"),              'date_rqst',     'dspurge',  7,  0,  'G'],
         'N' : ['COUNTRY',      "country",                             'country',       'wuser',    0,  0,  'G'],
         'O' : ['ORGTYPE',      "org_type",                            'org_type',      'wuser',    7,  0,  'G'],
         'P' : ['PROCESSBY',    "specialist",                          'specialist',    'dspurge',  9,  0,  'G'],
         'Q' : ['QUARTER',      "quarter",                             'quarter',       'dspurge',  7,  0,  'G'],
         'R' : ['RQSTDETAIL',   "rinfo",                               'rinfo',         'dspurge',  0,  0,  'G'],
         'S' : ['FROM',         "fromflag",                            'fromflag',      'dspurge',  0,  0,  'G'],
         'T' : ['DATASET',      "dspurge.dsid",                        'dspurge.dsid',  'dspurge',  0,  0,  'G'],
         'V' : ['RINDEX',       "dspurge.rindex",                      'dspurge.rindex','dspurge',  0,  0,  'G'],
         'W' : ['RTYPE',        "rqsttype",                            'rqsttype',      'dspurge',  5,  0,  'G'],
         'Y' : ['YEAR',         self.fmtyr("date_rqst"),              'date_rqst',     'dspurge',  4,  0,  'G'],
         'A' : ['DSCOUNT',      "dspurge.dsid",                        'A',             'dspurge', -7, -1,  'D'],
         'B' : ['MBYTERQST',    "round(sum(size_request)/1000000, 4)", 'B',             'dspurge', -14, 3,  'S'],
         'F' : ['MBINPUT',      "round(sum(size_input)/1000000, 4)",   'F',             'dspurge', -14, 3,  'S'],
         'C' : ['#UNIQUSER',    "dspurge.email",                       'C',             'dspurge', -9, -1,  'D'],
         'H' : ['#FILERQST',    "count(fcount)",                       'H',             'dspurge', -9, -1,  'S'],
         'J' : ['#UNIQFILE',    "wfpurge.wfile",                       'J',             'wfpurge', -9, -1,  'D'],
         'Z' : ['#REQUEST',     "dspurge.rindex",                      'Z',             'dspurge', -8, -1,  'D'],
         'X' : ['INDEX',        "",                                    'X',             '',        -6,  0,  ' ']
      }
      # keys EXPAND - short field names allow zero usage
      # column 0   - expand ID for group of fields
      # column 1   - field name shown in where condition query string
      # column 2   - field name in format as shown in select clauses
      # column 3   - table name that the field belongs to 
      self.EXPAND = {
      # SHRTNM EXPID     CNDSTR    FIELDNAME       TBLNAM
         'D' : ["TIME",   "dDmy"],
         'M' : ["TIME",   "dDmy"],
         'Q' : ["TIME",   "dDmy"],
         'Y' : ["TIME",   "dDmy"],
         'E' : ["USER",   "eilgco",  "email",        "wuser"],
         'I' : ["USER",   "eilgco",  "fstname",      "wuser"],
         'L' : ["USER",   "eilgco",  "lstname",      "wuser"],
         'G' : ["USER",   "eilgco",  "org_name",     "wuser"],
         'O' : ["USER",   "eilgco",  "org_type",     "wuser"],
         'N' : ["USER",   "eilgco",  "country",      "wuser"],
         'T' : ["FILE",   "StT", "rcrqst.dsid",   "rcrqst"],
         'U' : ["FILE",   "StT", "dsowner.specialist", "dsowner"],
         'S' : ["FROM",   "s",   "fromflag",     "dspurge"],
         'W' : ["RTYPE",  "M",   "rqsttype",     "dspurge"],
      }
      # valid options for params, a hash array of command line parameters
      #   a -- 1 to view all usage info available
      #   A -- number or records to return
      #   c -- array of specified country codes
      #   C -- a string of short field names for viewing usages
      #   d -- array of specified dates 
      #   D -- dates range, array of 1 or 2 dates in format of YYYY-MM-DD
      #   e -- array of specified email addresses
      #   E -- use given date or date range for email notice of data update
      #   f -- array of specified WEB Online file names
      #   F -- file name range, array of 1 or 2 file names
      #   g -- array of specified orginization names
      #   h -- for give emails, include their histical emails registered before
      #   H -- a string of report title to replace the default one
      #   i -- array of specified first names
      #   I -- use given email IDs for email notice of data update
      #   l -- array of specified last names
      #   L -- column delimiter for output
      #   m -- array of specified months 
      #   M -- array of specified request types
      #   N -- number read range, arrage of 1 or 2 integers
      #   o -- array of specified orginization types
      #   O -- a string of short field names for sorting on
      #   q -- array of the specified quarters, normally combined with years
      #   s -- array of from-flags the requests are initiated
      #   S -- array of login names of specialists who own the requests
      #   t -- array of specified dataset names
      #   T -- dataset range, array of 1 or 2 dataset names
      #   U -- use given unit for file or data sizes
      #   v -- aray of specified request indices
      #   w -- generate view without totals
      #   y -- array of specified years
      #   z -- generate view including entries with zero usage
      self.params = {}
      # relationship between parameter options and short field names, A option is not
      # related to a field name if it is not in keys SNS 
      self.SNS = {
         'c' : 'N', 'd' : 'D', 'D' : 'D', 'e' : 'E', 'f' : 'U', 'F' : 'U',
         'g' : 'G', 'i' : 'I', 'l' : 'L', 'm' : 'M', 'M' : 'W', 'N' : 'H',
         'o' : 'O', 'q' : 'Q', 's' : 'S', 'S' : 'P', 't' : 'T', 'T' : 'T',
         'v' : 'V', 'y' : 'Y'
      }
      self.tablenames = self.fieldnames = self.condition = ''
      self.sfields = []
      self.gfields = []
      self.dfields = []
      self.pgname = 'viewallusage'
      self.rsname = "size_request"

   # function to read parameters
   def read_pararmeters(self):
      self.view_dbinfo()
      argv = sys.argv[1:]
      inputs = []
      option = 'C'   # default option
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
            if val != '!':
               if option == 's':
                  val = int(val)*1000000    # convert MBytes to Bytes
               elif option in self.SNS:
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
      if 'o' not in self.params:
         if 'e' not in self.params:
            self.params['o'] = ['!', "'DSS'"]   # default to exclude 'DSS' for organization
      elif self.params['o'][0] == "'ALL'":
         del self.params['o']

   # function to start actions
   def start_actions(self):
      usgtable = 'dspurge'
      self.build_query_strings(usgtable)  # build tablenames, fieldnames, and conditions
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
      cols = self.params['C'][0] if 'C' in self.params else 'X'
      if cols == 'X': self.pglog("{}: miss field names '{}'".format(self.pgname, self.VUSG['SNMS']), self.LGWNEX)
      if cols.find('Q') > -1 and cols.find('Y') < 0:   # add Y if Q included
         cols = re.sub('Q', 'YQ', cols)
         self.params['C'][0] = cols
      if cols.find('J') > -1 and (cols.find('B') > -1 or cols.find('F') > -1):
         self.pglog(self.pgname + ": CANNOT view unique file counts with total data sizes", self.LGWNEX)
      for sn in cols:
         if sn == 'X': continue  # do not process INDEX field
         if self.VUSG['SNMS'].find(sn) < 0:
            self.pglog("{}: Field {} must be in field names '{}X'".format(self.pgname, sn, self.VUSG['SNMS']), self.LGWNEX)
         if 'z' not in self.params or sn in self.EXPAND: continue
         fld = self.FLDS[sn]
         if fld[6] != 'G': continue
         self.pglog("{}: cannot show zero usage for unexpandable field {} - {}".formt(self.pgname, sn, fld[0]), self.LGWNEX)
      if 'E' in self.params or 'I' in self.params:
         if 'z' in self.params:
            self.pglog(self.pgname + ": option -z and -E/-I can not be present at the same time", self.LGWNEX)
         elif 't' not in self.params or len(self.params['t']) > 1:
            self.pglog(self.pgname + ": specify one dataset for viewing usage of notified users", self.LGWNEX)
         elif 'E' in self.params and 'I' in self.params:
            self.pglog(self.pgname + ": option -E and -I can not be present at the same time", self.LGWNEX)
      if cols.find('F') > -1:
         ms = re.search(r'([USJ])', cols)
         if ms:
            self.pglog("{}: Canot get column F (input sizes) with column {}".format(self.pgname, ms.group(1)), self.LGWNEX)
         else:
            ms = re.search(r'([fFs])', self.params)
            if ms: self.pglog("{}: Canot get column F (input sizes) for option -{}".format(self.pgname, ms.group(1)), self.LGWNEX)
   
      if cols.find('B') > -1 and (re.search(r'[UJ]', cols) or 'f' in self.params or 'F' in self.params):
         self.rsname = "size"
         self.FLDS['B'][3] = "wfpurge"
         if 'U' not in self.params: self.params['U'] = ['M']
   
      for opt in self.params:
         if self.VUSG['CNDS'].find(opt) > -1: return
      self.pglog("{}: miss condition options '{}'".format(self.pgname, self.VUSG['CNDS']), self.LGWNEX)
   
   # process parameter options to build all query strings
   # global variables are used directly and nothing passes in and returns back
   def build_query_strings(self, usgtable):
      # initialize query strings
      joins = having = groupnames = ''
      self.tablenames = usgtable
      cols = self.params['C'][0]
      if 'U' in self.params:    # reset units for file and read sizes
         if cols.find('B') > -1: self.FLDS['B'] = self.set_data_unit(self.FLDS['B'], self.params['U'][0], "sum({})".format(self.rsname))
         if cols.find('S') > -1: self.FLDS['F'] = self.set_data_unit(self.FLDS['F'], self.params['U'][0], "size_input")
      if 'e' in self.params and 'h' in self.params: self.params['e'] = self.include_historic_emails(self.params['e'], 3)
      for opt in self.params:
         if self.VUSG['NOPT'].find(opt) > -1: continue
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
      if 'E' in self.params or 'I' in self.params:
         (self.tablenames, joins) = self.join_query_tables("emreceive", self.tablenames, joins, usgtable)
      if joins:
         if self.condition:
            self.condition = "{} AND {}".format(joins, self.condition)
         else:
            self.condition = joins
      if 'n' in self.params: self.condition += " AND location > ' '"
      if 'E' in self.params or 'I' in self.params:
         self.condition += self.notice_condition(self.params['E'], self.params['I'], self.params['t'][0])
      if groupnames and self.sfields: self.condition += " GROUP BY " + groupnames
      if having: self.condition += " HAVING " + having
   
   # exand records as needed
   def expand_records(self, records):
      recs = self.expand_query("TIME", records, self.params, self.EXPAND)
      trecs = self.expand_query("USER", records, self.params, self.EXPAND, self.VUSG, self.SNS, self.FLDS)
      if trecs: self.crosshash(recs, trecs)
      trecs = self.expand_query("FILE", records, self.params, self.EXPAND, self.VUSG, self.SNS, self.FLDS)
      if trecs: recs = self.crosshash(recs, trecs)
      trecs = self.expand_query("METHOD", records, self.params, self.EXPAND, self.VUSG, self.SNS, self.FLDS)
      if trecs: recs = self.crosshash(recs, trecs)
      return self.joinhash(records, recs, 0, 1)

# main function to excecute this script
def main():
   object = ViewRQSTUsage()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
