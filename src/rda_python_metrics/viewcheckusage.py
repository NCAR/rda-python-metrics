#!/usr/bin/env python3
#
###############################################################################
#
#     Title : viewcheckusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/15/2022
#             2025-03-27 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to view historical information of command activities
#             controlled by utility prgoram dscheck.
#
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
###############################################################################
#
import os
import re
import sys
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgDBI
from . import PgView

VUSG = {
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
FLDS = {
# SHRTNM COLUMNNANE      FIELDNAME                         CNDNAME        TBLNAM       Size Prc Grp/Sum
   'A' : ['ARGV',         "argv",                           'argv',        'dschkhist',  0,  0,  'G'],
   'C' : ['COMMAND',      "command",                        'command',     'dschkhist',  0,  0,  'G'],
   'D' : ['DATE',         "date",                           'date',        'dschkhist', 10,  0,  'G'],
   'E' : ['ERRMSG',       "errmsg",                         'errmsg',      'dschkhist',  0,  0,  'G'],
   'H' : ['HOSTNAME',     "hostname",                       'hostname',    'dschkhist',  0,  0,  'G'],
   'I' : ['CHKIDX',       "cindex",                         'cindex',      'dschkhist',  0,  0,  'G'],
   'K' : ['TIME',         "time",                           'time',        'dschkhist',  8,  0,  'G'],
   'L' : ['BATCHID',      "bid",                            'bid',         'dschkhist',  0,  0,  'G'],
   'M' : ['MONTH',        PgDBI.fmtym("date"),              'date',        'dschkhist',  7,  0,  'G'],
   'G' : ['TRIED',        "tcount",                         'tcount',      'dschkhist',  0,  0,  'G'],
   'P' : ['DATAPROC',     "size",                           'size',        'dschkhist', -14, -1, 'G'],
   'Q' : ['QUETIME',      "quetime",                        'quetime',     'dschkhist',  0,  0,  'G'],
   'R' : ['RUNTIME',      "ttltime",                        'ttltime',     'dschkhist',  0,  0,  'G'],
   'S' : ['SPECIALIST',   "specialist",                     'specialist',  'dschkhist',  9,  0,  'G'],
   'T' : ['DATASET',      "dsid",                           'dsid',        'dschkhist',  0,  0,  'G'],
   'N' : ['AN',           "action",                         'action',      'dschkhist',  2,  0,  'G'],
   'W' : ['STATUS',       "status",                         'status',      'dschkhist',  5,  0,  'G'],
   'Y' : ['YEAR',         PgDBI.fmtyr("date"),              'date',        'dschkhist',  4,  0,  'G'],
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
EXPAND = {
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
params = {}
# relationship between parameter options and short field names, A option is not
# related to a field name if it is not in keys %SNS 
SNS = {
   'b' : 'L', 'B' : 'L', 'c' : 'C', 'd' : 'D', 'D' : 'D', 'h' : 'H', 'i' : 'I', 'm' : 'M', 'n' : 'N',
   'q' : 'Q', 'r' : 'R', 'q' : 'Q', 's' : 'W', 'S' : 'S', 't' : 'T', 'T' : 'T', 'y' : 'Y'
}

tablenames = fieldnames = condition = ''
sfields = []
gfields = []
dfields = []
pgname = 'viewcheckusage'

#
# main function to run this program
#
def main():

   PgDBI.view_dbinfo()
   argv = sys.argv[1:]
   inputs = []
   option = 'C'

   for arg in argv:
      if re.match(r'^-.*$', arg):
         curopt = arg[1:2]
         if curopt and VUSG['OPTS'].find(curopt) > -1:
            if VUSG['NOPT'].find(option) > -1:
               params[option] = 1
            elif inputs:
               params[option]= inputs   # record input array
               inputs = []      # empty input array
            option = curopt     # start a new option
         else:
            PgLOG.pglog(arg + ": Unknown Option", PgLOG.LGWNEX)
      else:
         val = arg
         if val != '!' and option in SNS:
            sfld = SNS[option]
            if VUSG['SFLD'].find(sfld) > -1:
               if VUSG['UFLD'].find(sfld) > -1:
                  val = arg.upper()     # in case not in upper case
               elif VUSG['LFLD'].find(sfld) > -1:
                  val = arg.lower()     # in case not in lower case
               if option == 'c':
                  val = PgView.get_country_name(val)
               elif option == 't' or option == 'T':
                  val = PgUtil.format_dataset_id(val)   # add 'ds' if only numbers
               val = "'{}'".format(val)
         inputs.append(val)
   
   # record the last option
   if VUSG['NOPT'].find(option) > -1:
      params[option] = 1
   elif inputs:
      params[option] = inputs   # record input array
   
   if not params:
      PgLOG.show_usage(pgname)
   else:
      check_enough_options()

   usgtable = 'dschkhist'
   build_query_strings(usgtable)   # build tablenames, fieldnames, and condtions
   records = PgDBI.pgmget(tablenames, fieldnames, condition, PgLOG.UCLWEX)
   if not records: PgLOG.pglog("No Usage Found For Given Conditions", PgLOG.LGWNEX)
   totals = None if 'w' in params else {}
   if dfields or totals != None:
      records = PgView.compact_hash_groups(records, gfields, sfields, dfields, totals)
   if 'z' in params: records = expand_records(records)
   ostr = params['O'][0] if 'O' in params else params['C'][0]
   records = PgView.order_records(records, ostr.replace('X', ''))
   PgView.simple_output(params, FLDS, records, totals)

   PgLOG.pgexit(0)

#
# check if enough information entered on command line for generate view/report, exit if not
#
def check_enough_options():
   
   flds = params['C'][0] if 'C' in params else 'X'
   if flds == 'X': PgLOG.pglog("{}: MISS short field names '{}'".format(pgname, VUSG['SNMS']), PgLOG.LGWNEX)

   for sn in flds:
      if sn == 'X': continue  # do not process INDEX field
      if VUSG['SNMS'].find(sn) == -1:
         PgLOG.pglog("{}: Field sn must be in short field names: {}X".format(pgname, VUSG['SNMS']), PgLOG.LGWNEX)

      if 'z' not in params or sn in EXPAND: continue
      fld = FLDS[sn]
      if fld[6] != 'G': continue
      PgLOG.pglog("{}: cannot show zero usage for unexpandable field {} - {}".format(pgname, sn, fld[0]), PgLOG.LGWNEX)


   for arg in params:
      if arg in VUSG['CNDS']: return

   PgLOG.pglog("{}: miss condition options '{}'".format(pgname, VUSG['CNDS']), PgLOG.LGWNEX)

#
# process parameter options to build all query strings
# global variables are used directly and nothing passes in and returns back
#
def build_query_strings(usgtable):

   global condition, fieldnames, tablenames
   joins = having = ordernames = groupnames = ''
   tablenames = usgtable
   cols = params['C'][0]

   if 'U' in params:    # reset units for file and read sizes
      if cols.find('B') > -1: FLDS['B'] = PgView.set_data_unit(FLDS['B'], params['U'][0], "sum(size)")
      if cols.find('P') > -1: FLDS['P'] = PgView.set_data_unit(FLDS['P'], params['U'][0], "size")

   for opt in params:
      if opt == 'O' or VUSG['NOPT'].find(opt) > -1: continue
      if opt == 'C':   # build field, table and group names
         for sn in cols:
            if sn == 'X': continue  # do not process INDEX field
            fld = FLDS[sn]
            if fieldnames: fieldnames += ', '
            fieldnames += "{} {}".format(fld[1], sn)   # add to field name string
            (tablenames, joins) = PgView.join_query_tables(fld[3], tablenames, joins, usgtable)
            if fld[6] == 'S':
               sfields.append(sn)
            else:
               if groupnames: groupnames += ', '
               groupnames += sn     # add to group name string
               if fld[6] == 'D':
                  dfields.append(sn)
               else:
                  gfields.append(sn)
      elif opt == 'O':
         continue   # order records later
      elif VUSG['CNDS'].find(opt) > -1:
         sn = SNS[opt]
         fld = FLDS[sn]
         # build having and where conditon strings
         cnd = PgView.get_view_condition(opt, sn, fld, params, VUSG)
         if cnd:
            if VUSG['HCND'].find(opt) > -1:
               if having: having += ' AND '
               having += cnd
            else:
               if condition: condition += ' AND '
               condition += cnd
            (tablenames, joins) = PgView.join_query_tables(fld[3], tablenames, joins, usgtable)

   # append joins, group by, order by, and having strings to condition string
   if joins:
      if condition:
         condition = "{} AND {}".format(joins, condition)
      else:
         condition = joins
   if groupnames and sfields: condition += " GROUP BY " + groupnames
   if having: condition += " HAVING " + having

def expand_records(records):
   
   recs = PgView.expand_query("TIME", records, params, EXPAND)

   trecs = PgView.expand_query("CHECK", records, params, EXPAND, VUSG, SNS, FLDS)
   recs = PgUtil.crosshash(recs, trecs)

   return PgUtil.joinhash(records, recs, 0, 1)

#
# call main() to start program
#
if __name__ == "__main__": main()
