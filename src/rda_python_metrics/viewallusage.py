#!/usr/bin/env python
###############################################################################
#     Title : viewallusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/01/2022
#             2025-03-27 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-19 convert to class ViewALLUsage
#   Purpose : python program to view all usage information.
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import os
import re
import sys
from .pg_view import PgView

class ViewALLUsage(PgView):

   def __init__(self):
      super().__init__()
      self.VUSG = {
         'SNMS' : "ABCDEFGHKMNOPQRSTUVWY",            # all available short field names in FLDS
         'OPTS' : 'AabcCdDeEfghHIkmnLMNoOqsStTUvVwyz', # all available options, used for self.params
         'NOPT' : 'abhwz',                            # stand alone option without inputs
         'ACND' : 'cdefgkmMoqStvy',                   # available array condition options
         'RCND' : 'DsNT',                             # available range condition options
         'CNDS' : 'acdDeEfgkmMnNoqsStTvVy',           # condition options, ACND, RCND and 'a'
         'HCND' : 'N',                                # condition options for having clause
         'ECND' : 'my',                               # condition options need evaluating
         'TCND' : 'dDmy',                             # temporal condition options
         'SFLD' : 'DEFGKNOPTVW',                      # string fields, to be quoted in condition
         'UFLD' : 'GNOVW',                            # string fields must be in upper case
         'LFLD' : 'EPT'                               # string fields must be in lower case
      }
      # keys FLDS - short field names
      # column 0   - column title showing in usage view
      # column 1   - field name in format as shown in select clauses
      # column 2   - field name shown in where condition query string
      # column 3   - table name that the field belongs to 
      # column 4   - output field length, the longer one of data size and comlun title, determine
      #              dynamically if it is 0. Negative values indicate right justification
      # column 5   - precision for floating point value if positive and an integer value if -1
      # column 6   - field flag to indicate it is a group, distinct or sum field
      self.FLDS = {
      # SHRTNM COLUMNNANE   FIELDNAME                         CNDNAME       TBLNAM        Size Prc Grp/Sum
         'D' : ['DATE',      "date",                           'date',       'allusage',  10,   0,  'G'],
         'E' : ['EMAIL',     "allusage.email",        'allusage.email',      'allusage',   0,   0,  'G'],
         'F' : ['FORMAT',    "data_format",                    'data_format', 'dataset',   0,   0,  'G'],
         'M' : ['MONTH',     self.fmtym("date"),              'date',       'allusage',   7,   0,  'G'],
         'N' : ['COUNTRY',   "country",                        'country',    'allusage',   0,   0,  'G'],
         'K' : ['REGION',    "region",                         'region',     'allusage',   0,   0,  'G'],
         'G' : ['GROUP',     "source",                         'source',     'allusage',   0,   0,  'G'],
         'O' : ['ORGTYPE',   "org_type",                       'org_type',   'allusage',   7,   0,  'G'],
         'P' : ['DSOWNER',   "specialist",                     'specialist', 'dsowner',    8,   0,  'G'],
         'Q' : ['QUARTER',   "quarter",                        'quarter',    'allusage',   7,  -1,  'G'],
         'R' : ['DSTITLE',   "search.datasets.title", 'search.datasets.title',   'search.datasets',   0,   0,  'G'],
         'S' : ['BYTESIZE',  "size",                           'size',       'allusage', -14,  -1,  'G'],
         'T' : ['DATASET',   "allusage.dsid",         'allusage.dsid',       'allusage',   0,   0,  'G'],
         'V' : ['IPADDRESS', "ip",                             'ip',         'allusage',   15,  0,  'G'],
         'W' : ['METHOD',    "method",                         'method',     'allusage',   6,   0,  'G'],
         'Y' : ['YEAR',      self.fmtyr("date"),              'date',       'allusage',   4,   0,  'G'],
         'A' : ['DSCOUNT',   "allusage.dsid",                  'A',          'allusage',  -7,  -1,  'D'],
         'B' : ['MBYTEREAD', "round(sum(size)/(1000000), 4)",  'B',          'allusage', -14,   3,  'S'],
         'C' : ['#UNIQUSER', "allusage.email",                 'C',          'allusage',  -9,  -1,  'D'],
         'H' : ['#READ',     "count(*)",                       'H',          'allusage',  -8,  -1,  'S'],
         'U' : ['#UNIQIP',   "ip",                             'U',          'allusage',  -9,  -1,  'D'],
         'X' : ['INDEX',     "",                               'X',          '',          -6,  -1,  ' ']
      }
      
      # keys EXPAND - short field names allow zero usage
      # column 0   - expand ID for group of fields
      # column 1   - field name shown in where condition query string
      # column 2   - field name in format as shown in select clauses
      # column 3   - table name that the field belongs to 
      self.EXPAND = {
      # SHRTNM EXPID     CNDSTR    FIELDNAME   TBLNAM
         'D' : ["TIME",   "dDmy"],
         'M' : ["TIME",   "dDmy"],
         'Q' : ["TIME",   "dDmy"],
         'Y' : ["TIME",   "dDmy"],
      
         'E' : ["USER",   "ecko",  "email",     "wuser",  "user"],
         'O' : ["USER",   "ecko",  "org_type",  "wuser",  "user"],
         'N' : ["USER",   "ecko",  "country",   "wuser",  "user"],
         'K' : ["USER",   "ecko",  "region",    "wuser",  "user"],
      
         'R' : ["DSID",   "fFsStT", "search.datasets.title", "search.datasets"],
         'T' : ["DSID",   "fFsStT", "dataset.dsid",   "dataset"],
         'P' : ["DSID",   "fFsStT", "specialist",     "dsowner"],
      
         'W' : ["METHOD", "gM",      "method",         "allusage"],
         'G' : ["METHOD", "gM",      "source",         "allusage"]
      }
      # valid options for self.params, a hash array of command line parameters
      #   a -- 1 to view all usage info available
      #   A -- number or records to return
      #   c -- array of specified country codes
      #   C -- a string of short field names for viewing usages
      #   d -- array of specified dates 
      #   D -- dates range, array of 1 or 2 dates in format of YYYY-MM-DD
      #   e -- array of specified email addresses
      #   E -- use given date or date range for email notice of data update
      #   f -- use given data format to specify datasets.data_format
      #   g -- array of data usage source groups
      #   h -- for give emails, include their histical emails registered before
      #   H -- a string of report title to replace the default one
      #   I -- use given email IDs for email notice of data update
      #   k -- array of specified region names
      #   L -- column delimiter for output
      #   m -- array of specified months 
      #   M -- array of specified download methods
      #   N -- number read range, arrage of 1 or 2 integers
      #   o -- array of specified orginization types
      #   O -- a string of short field names for sorting on
      #   q -- array of the specified quarters, normally combined with years
      #   s -- file size range, arrage of 1 or 2 sizes in unit of MByte
      #   S -- array of login names of specialists who owns the datasets
      #   t -- array of specified dataset names
      #   T -- dataset range, array of 1 or 2 dataset names
      #   U -- use given unit for file or data sizes
      #   v -- array of specified IP addresses
      #   V -- IP address range
      #   w -- generate view without totals
      #   y -- array of specified years 
      #   z -- generate view including entries without usage
      self.params = {}
      # relationship between parameter options and short field names, A option is not
      # related to a field name if it is not in keys SNS 
      self.SNS = {
         'c' : 'N', 'd' : 'D', 'D' : 'D', 'e' : 'E', 'f' : 'F', 'g' : 'G', 'm' : 'M',
         'M' : 'W', 'N' : 'H', 'k' : 'K', 'o' : 'O', 'q' : 'Q', 's' : 'S', 'S' : 'P',
         't' : 'T', 'T' : 'T', 'u' : 'U', 'v' : 'V', 'V' : 'V', 'y' : 'Y'
      }
      self.tablenames = self.fieldnames = self.condition = ''
      self.sfields = []
      self.gfields = []
      self.dfields = []
      self.pgname = 'viewallusage'

   # function to read parameters
   def read_parameters(self):
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
                  self.params[option] = inputs   # record input array
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
      usgtable = 'allusage'
      years = self.build_year_list(self.params, self.VUSG)
      self.build_query_strings(usgtable)   # build tablenames, fieldnames, and condtions
      records = None
      for year in sorted(years):
         tname = "{}_{}".format(usgtable, year)
         tbls = self.tablenames.replace(usgtable, tname)
         flds = self.fieldnames.replace(usgtable, tname)
         cond = self.condition.replace(usgtable, tname)
         pgrecs = self.pgmget(tbls, flds, cond, self.UCLWEX)
         if pgrecs:
            if records:
               for fld in records: records[fld].extend(pgrecs[fld])
            else:
               records = pgrecs
      if not records: self.pglog("No Usage Found For Given Conditions", self.LGWNEX)
      totals = None if 'w' in self.params else {}
      if self.dfields or totals != None or len(years) > 1:
         records = self.compact_hash_groups(records, self.gfields, self.sfields, self.dfields, totals)
      if 'z' in self.params: records = self.expand_records(records)
      ostr = self.params['O'][0] if 'O' in self.params else self.params['C'][0]
      records = self.order_records(records, ostr.replace('X', ''))
      self.simple_output(self.params, self.FLDS, records, totals)
   
   # cehck if enough information entered on command line for generate view/report, exit if not
   def check_enough_options(self):
      cols = self.params['C'][0] if 'C' in self.params else 'X'
      if cols == 'X': self.pglog("{}: miss field names '{}'".format(self.pgname, self.VUSG['SNMS']), self.LGWNEX)
      if cols.find('Q') > -1 and cols.find('Y') < 0:   # add Y if Q included
         cols = re.sub('Q', 'YQ', cols)
         self.params['C'][0] = cols
      for sn in cols:
         if sn == 'X': continue  # do not process INDEX field
         if self.VUSG['SNMS'].find(sn) < 0:
            self.pglog("{}: Field {} must be in short field names '{}X'".format(self.pgname, sn, self.VUSG['SNMS']), self.LGWNEX)
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
         if cols.find('B') > -1: self.FLDS['B'] = self.set_data_unit(self.FLDS['B'], self.params['U'][0], "sum(size)")
         if cols.find('S') > -1: self.FLDS['S'] = self.set_data_unit(self.FLDS['S'], self.params['U'][0], "size")      
      if 'e' in self.params and 'h' in self.params: self.params['e'] = self.include_historic_emails(self.params['e'], 3)
      for opt in self.params:
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
            if self.VUSG['NOPT'].find(opt) > -1: continue
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
      if 'E' in self.params or 'I' in self.params:
         self.condition += self.notice_condition(self.params['E'], self.params['I'], self.params['t'][0])
      if groupnames and self.sfields: self.condition += " GROUP BY " + groupnames
      if having: self.condition += " HAVING " + having
   
   # exand records as needed
   def expand_records(self, records):
      recs = self.expand_query("TIME", records, self.params, self.EXPAND)
      trecs = self.expand_query("USER", records, self.params, self.EXPAND, self.VUSG, self.SNS, self.FLDS)
      recs = self.crosshash(recs, trecs)
      trecs = self.expand_query("DSID", records, self.params, self.EXPAND, self.VUSG, self.SNS, self.FLDS)
      recs = self.crosshash(recs, trecs)
      trecs = self.expand_query("OWNER", records, self.params, self.EXPAND, self.VUSG, self.SNS, self.FLDS)
      recs = self.crosshash(recs, trecs)
      trecs = self.expand_query("METHOD", records, self.params, self.EXPAND, self.VUSG, self.SNS, self.FLDS)
      recs = self.crosshash(recs, trecs)
      return self.joinhash(records, recs, 0, 1)

# main function to excecute this script
def main():
   object = ViewALLUsage()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
