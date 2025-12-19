#!/usr/bin/env python3
###############################################################################
#     Title : viewwebfile
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/15/2022
#             2025-03-28 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#             2025-12-19 convert to class ViewWEBFile
#   Purpose : python program to view info for web online files
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import os
import re
import sys
from .pg_view import PgView

class ViewWEBFile(PgView):

   def __init__(self):
      super().__init__()
      self.FILE = {
         'SNMS' : "BCDEFGHIJKLMNOPQRSTUVWYZ",    # all available short field names in %FLDS
         'OPTS' : 'AabCdDefFgGHijJlLmMnNoOprsStTuUvwyYzZ',  # all available options, used for %params
         'NOPT' : 'abjJw',                       # stand alone option without inputs
         'ACND' : 'defgGilmMnopStuvyYz',         # available array condition options
         'RCND' : 'DFNrsTZ',                     # available range condition options
         'CNDS' : 'adDefFgGilmMnNoprstTuvyYzZ',  # condition options, ACND, RCND and 'a'
         'ECND' : 'mMyY',                        # condition options need evaluating
         'SFLD' : 'DEFILNOPQTUVZ',               # string fields, to be quoted in condition
         'UFLD' : 'ILOPV',                       # string fields must be in upper case
         'LFLD' : 'EQTU'                         # string fields must be in lower case
      }
      # keys %FLDS - short field names
      # column 0   - column title showing in mss file view
      # column 1   - field name in format as shown in select clauses
      # column 2   - field name shown in where condition query string
      # column 3   - table name that the field belongs to
      # column 4   - output field length, the longer one of data size and comlun title, determine
      #              dynamically if it is 0. Negative values indicate right justification
      # column 5   - precision for floating point value if positive and show total value if not zero
      # column 6   - field flag to indicate it is a group, distinct or sum field
      self.FLDS = {
      # SHRTNM COLUMNNANE      FIELDNAME                              CNDNAME          TBLNAM     Size Prc Grp/Sum
         'D' : ['DATEWRITE',    "date_modified",                       'date_modified', 'wfile',   0,  0,  'G'],
         'E' : ['EMAIL',        "email",                               'email',         'user',    0,  0,  'G'],
         'F' : ['FILENAME',     "wfile",                               'wfile',         'wfile',   0,  0,  'G'],
         'G' : ['PRODUCT',      "tindex",                              'tindex',        'wfile',   0,  0,  'G'],
         'H' : ['CMONTH',       self.fmtym("date_created"),           'date_created',  'wfile',   7,  0,  'G'],
         'I' : ['FIRSTNAME',    "fstname",                             'fstname',       'user',    0,  0,  'G'],
         'K' : ['CYEAR',        self.fmtyr("date_created"),           'date_created',  'wfile',   5,  0,  'G'],
         'L' : ['LASTNAME',     "lstname",                             'lstname',       'user',    0,  0,  'G'],
         'M' : ['WMONTH',       self.fmtym("date_modified"),          'date_modified', 'wfile',   7,  0,  'G'],
         'N' : ['DSCREATED',    "date_create",                         'date_create',   'dataset',10,  0,  'G'],
         'P' : ['TYPE',         "wfile.type",                          'wfile.type',    'wfile',   4,  0,  'G'],
         'O' : ['STAT',         "status",                               'status',       'wfile',   4,  0,  'G'],
         'Q' : ['DSOWNER',      "specialist",                          'specialist',    'dsowner', 8,  0,  'G'],
         'R' : ['DSTITLE',      "search.datasets.title", 'search.datasets.title', 'search.datasets', 0,  0,  'G'],
         'S' : ['FILESIZE',     "data_size",                           'data_size',     'wfile', -14, -1,  'G'],
         'T' : ['DATASET',      "wfile.dsid",                          'wfile.dsid',    'wfile',   0,  0,  'G'],
         'U' : ['SPECIALIST',   "logname",                             'logname',       'user',   10,  0,  'G'],
         'V' : ['DSARCH',       "use_rdadb",                           'use_rdadb',     'dataset', 6,  0,  'G'],
         'W' : ['DSTYPE',       "search.datasets.type",  'search.datasets.type', 'search.datasets', 6,  0,  'G'],
         'Y' : ['WYEAR',        self.fmtyr("date_modified"),          'date_modified', 'wfile',   5,  0,  'G'],
         'Z' : ['DATECREATE',   "date_created",                        'date_created',  'wfile',  10,  0,  'G'],
         'A' : ['DSCOUNT',      "wfile",                               'A',             'wfile',  -7, -1,  'D'],
         'B' : ['MBYTEDATA',    "round(sum(data_size)/(1000000), 4)",  'B',             'wfile', -14,  3,  'S'],
         'C' : ['#UNIQSPLST',   "uid",                                 'C',             'wfile', -10, -1,  'D'],
         'J' : ['#UNIQFILE',    "wid",                                 'J',             'wfile',  -9, -1,  'D'],
         'X' : ['INDEX',        "",                                    'X',             '',       -6,  0,  ' ']
      }
      # valid options for %params, a hash array of command line parameters
      #   a -- 1 to view all usage info available
      #   A -- number or records to return
      #   C -- a string of short field names for viewing usages
      #   d -- array of specified dates of file last written
      #   D -- last written dates range, array of 1 or 2 dates in format of YYYY-MM-DD
      #   e -- array of specified email addresses
      #   f -- array of specified online file names
      #   F -- file name range, array of 1 or 2 file names
      #   g -- array of specified top group indices
      #   G -- array of specified top group IDs
      #   H -- a string of report title to replace the default one
      #   i -- array of specified first names
      #   j -- 1 to include group ID for GROUP
      #   J -- 1 to include group title for GROUP
      #   l -- array of specified last names
      #   L -- column delimiter for output
      #   m -- array of specified months of file last written
      #   M -- array of specified months of file created
      #   n -- array of specified user numbers
      #   D -- dates range, datasets created between, array of 1 or 2 dates in format of YYYY-MM-DD
      #   o -- array of specified file status
      #   O -- a string of short field names for sorting on
      #   p -- array of web file types, Data, Document, and etc.
      #   r -- group index range, array of 1 or 2 group indices
      #   s -- file size range, arrage of 1 or 2 sizes in unit of MByte
      #   S -- specialist lognames who handle the datasets
      #   t -- array of specified dataset names
      #   T -- dataset range, array of 1 or 2 dataset names
      #   u -- array of specified specialist user names
      #   U -- use given unit for file or data sizes
      #   v -- array of specified use RDADB flags
      #   w -- generate view without totals
      #   y -- array of specified years of file last written
      #   Y -- array of specified years of file created
      #   z -- array of specified dates when files created
      #   Z -- created dates range, array of 1 or 2 dates in format of YYYY-MM-DD
      self.params = {}
      # relationship between parameter options and short field names, A option is not
      # related to a field name if it is not in keys %SNS
      self.SNS = {
         'd' : 'D', 'D' : 'D', 'e' : 'E', 'f' : 'F', 'F' : 'F', 'g' : 'G', 'i' : 'I',
         'l' : 'L', 'm' : 'M', 'M' : 'H', 'N' : 'N', 'o' : 'O', 'p' : 'P', 'r' : 'G',
         's' : 'S', 'S' : 'Q', 't' : 'T', 'T' : 'T', 'u' : 'U', 'v' : 'V', 'W' : 'W',
         'y' : 'Y', 'Y' : 'K', 'z' : 'Z', 'Z' : 'Z'
      }
      self.tablenames = self.fieldnames = self.condition = ''
      self.sfields = []
      self.gfields = []
      self.dfields = []
      self.pgname = 'viewwebfile'

   # function to read parameters
   def read_pararmeters(self):
      self.view_dbinfo()
      argv = sys.argv[1:]
      inputs = []
      option = 'C'   # default option
      for arg in argv:
         if re.match(r'^-.*$', arg):
            curopt = arg[1:2]
            if curopt and self.FILE['OPTS'].find(curopt) > -1:
               if self.FILE['NOPT'].find(option) > -1:
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
                  if self.FILE['SFLD'].find(sfld) > -1:
                     if self.FILE['UFLD'].find(sfld) > -1:
                        val = arg.upper()     # in case not in upper case
                     elif self.FILE['LFLD'].find(sfld) > -1:
                        val = arg.lower()     # in case not in lower case
                     if option == 'c':
                        val = self.get_country_name(val)
                     elif option == 't' or option == 'T':
                        val = self.format_dataset_id(val)
                     val = "'{}'".format(val)
            inputs.append(val)
      # record the last option
      if self.FILE['NOPT'].find(option) > -1:
         self.params[option] = 1
      elif inputs:
         self.params[option] = inputs   # record input array
      if not self.params:
         self.show_usage(self.pgname)
      else:
         self.check_enough_options()
   
   # function to start actions
   def start_actions(self):   
      usgtable = "wfile"
      self.build_query_strings(usgtable)  # build tablenames, fieldnames, and conditions
      records = self.pgmget(self.tablenames, self.fieldnames, self.condition, self.UCLWEX)
      if not records: self.pglog("No Usage Found For Given Conditions", self.LGWNEX)
      totals = None if 'w' in self.params else {}
      if self.dfields or totals != None:
         records = self.compact_hash_groups(records, self.gfields, self.sfields, self.dfields, totals)
      if 'j' in self.params or 'J' in self.params:
         j = 1 if 'j' in self.params else 0
         J = 1 if 'J' in self.params else 0
         records['g'] = self.expand_groups(records['g'], records['t'], j, J)
      ostr = self.params['O'][0] if 'O' in self.params else self.params['C'][0]
      records = self.order_records(records, ostr.replace('X', ''))
      self.simple_output(self.params, self.FLDS, records, totals)

   # cehck if enough information entered on command line for generate view/report, exit if not
   def check_enough_options(self):
      cols = self.params['C'][0] if 'C' in self.params else 'X'
      if cols == 'X': self.pglog("{}: miss field names '{}'".format(self.pgname, self.FILE['SNMS']), self.LGWNEX)
      for sn in cols:
         if sn == 'X': continue  # do not process INDEX field
         if self.FILE['SNMS'].find(sn) < 0:
            self.pglog("{}: Field {} must be in field names '{}X'".format(self.pgname, sn, self.FILE['SNMS']), self.LGWNEX)
      if 'g' in self.params or 'G' in self.params:
         if 't' not in self.params:
            self.pglog("Miss dataset condition via Option -t for processing Group", self.LGWNEX)
         elif len(self.params['t']) > 1:
            self.pglog("More than one dataset provided via Option -T for processing Group", self.LGWNEX)
         if 'G' in self.params:
            if 'g' not in self.params: self.params['g'] = []
            self.params['g'] = self.get_group_indices(self.params['G'], self.params['t'], self.params['g'])
            del self.params['G']
      if 'j' in self.params or 'J' in self.params:
         if cols.find('T') < 0: self.params['C'][0] += 'T'
         if cols.find('G') < 0: self.params['C'][0] += 'G'
      for opt in self.params:
         if self.FILE['CNDS'].find(opt) > -1: return
      self.pglog("{}: miss condition options '{}'".format(self.pgname, self.FILE['CNDS']), self.LGWNEX)

   # process parameter options to build all query strings
   # global variables are used directly and nothing passes in and returns back
   def build_query_strings(self, usgtable):
      # initialize query strings
      joins = groupnames = ''
      self.tablenames = usgtable
      cols = self.params['C'][0]
      if 'U' in self.params:    # reset units for file and read sizes
         if cols.find('B') > -1: self.FLDS['B'] = self.set_data_unit(self.FLDS['B'], self.params['U'][0], "sum(data_size)")
         if cols.find('S') > -1: self.FLDS['S'] = self.set_data_unit(self.FLDS['S'], self.params['U'][0], "data_size")
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
         elif self.FILE['CNDS'].find(opt) > -1:
            if self.FILE['NOPT'].find(opt) > -1: continue
            sn = self.SNS[opt]
            fld = self.FLDS[sn]
            # build having and where conditon strings
            cnd = self.get_view_condition(opt, sn, fld, self.params, self.FILE)
            if cnd:
               if self.condition: self.condition += ' AND '
               self.condition += cnd
               (self.tablenames, joins) = self.join_query_tables(fld[3], self.tablenames, joins, usgtable)
      # append joins, group by, and order by strings to condition string
      if self.condition:
         if 'o' not in self.params: self.condition += " AND status <> 'D'"
      else:
         self.condition = "status <> 'D'"
      if joins:
         if self.condition:
            self.condition = "{} AND {}".format(joins, self.condition)
         else:
            self.condition = joins
      if groupnames and self.sfields: self.condition += " GROUP BY " + groupnames

# main function to excecute this script
def main():
   object = ViewWEBFile()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
