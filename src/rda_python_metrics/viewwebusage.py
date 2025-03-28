#!/usr/bin/env python3
#
###############################################################################
#
#     Title : viewwebusage
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 03/15/2022
#             2025-03-28 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python program to view usage information for Web Online files.
#
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
###############################################################################
#
import os
import re
import sys
from rda_python_common import PgLOG
from rda_python_common import PgDBI
from rda_python_common import PgUtil
from . import PgView

VUSG = {
   'SNMS' : "ABCDEFGHIJKLMNOPRQTUVWYZ",   # all available short field names in %FLDS
   'OPTS' : 'AabcCdDeEfFhHiIklLmMNoOStTUvVwyz',  # all available options, used for %params
   'NOPT' : 'abhRwz',                     # stand alone option without inputs
   'ACND' : 'cdefiklmMoStvy',             # available array condition options
   'RCND' : 'DFNTV',                      # available range condition options
   'CNDS' : 'acdDefFiklmMNoStTvVy',       # condition options, ACND, RCND and 'a'
   'HCND' : 'N',                          # condition options for having clause
   'ECND' : 'my',                         # condition options need evaluating
   'TCND' : 'dDmy',                       # temporal condition options
   'SFLD' : 'DEFIKLNOPTVW',               # string fields, to be quoted in condition
   'UFLD' : 'ILNOW',                      # string fields must be in upper case
   'LFLD' : 'EPT'                         # string fields must be in lower case
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
FLDS = {
# SHRTNM COLUMNNANE      FIELDNAME                              CNDNAME        TBLNAM      Size Prc Grp/Sum
   'D' : ['DATE',         "date_read",                           'date_read',   'wusage',  10,  0,  'G'],
   'E' : ['EMAIL',        "wuser.email",                   'wuser.email',       'wuser',    0,  0,  'G'],
   'F' : ['FILENAME',     "wfile",                               'wfile',       'wfile',    0,  0,  'G'],
   'G' : ['PRODUCT',      "tindex",                              'tindex',      'wfile',    0,  0,  'G'],
   'I' : ['FIRSTNAME',    "fstname",                             'fstname',     'wuser',    0,  0,  'G'],
   'K' : ['ORGNAME',      "org_name",                            'org_name',    'wuser',    0,  0,  'G'],
   'Z' : ['TIME',         "time_read",                           'time_read',   'wusage',   8,  0,  'G'],
   'L' : ['LASTNAME',     "lstname",                             'lstname',     'wuser',    0,  0,  'G'],
   'M' : ['MONTH',        PgDBI.fmtym("date_read"),             'date_read',   'wusage',   7,  0,  'G'],
   'N' : ['COUNTRY',      "country",                             'country',     'wuser',    0,  0,  'G'],
   'O' : ['ORGTYPE',      "org_type",                            'org_type',    'wuser',    7,  0,  'G'],
   'P' : ['DSOWNER',      "specialist",                          'specialist',  'dsowner',  8,  0,  'G'],
   'Q' : ['QUARTER',      "quarter",                             'quarter',     'wusage',   7,  0,  'G'],
   'R' : ['DSTITLE',      "search.datasets.title", 'search.datasets.title',     'search.datasets', 0,  0,  'G'],
   'T' : ['DATASET',      "wusage.dsid",                  'wusage.dsid',        'wusage',   0,  0,  'G'],
   'V' : ['IPADDRESS',    "ip",                                  'ip',          'wusage',  15,  0,  'G'],
   'W' : ['METHOD',       "method",                              'method',      'wusage',   6,  0,  'G'],
   'Y' : ['YEAR',         PgDBI.fmtyr("date_read"),              'date_read',   'wusage',   4,  0,  'G'],
   'A' : ['DSCOUNT',      "wusage.dsid",                         'A',           'wusage',  -7, -1,  'D'],
   'B' : ['MBYTEREAD',    "round(sum(size_read)/1000000, 4)",    'B',           'wusage', -14,  3,  'S'],
   'C' : ['#UNIQUSER',    "wuid_read",                           'C',           'wusage',  -9, -1,  'D'],
   'H' : ['#READ',        "count(wusage.wid)",                   'H',           'wusage',  -8, -1,  'S'],
   'J' : ['#UNIQFILE',    "wusage.wid",                          'J',           'wusage',  -9, -1,  'D'],
   'U' : ['#UNIQIP',      "ip",                                  'U',           'wusage',  -9, -1,  'D'],
   'X' : ['INDEX',        "",                                    'X',           '',        -6,  0,  ' ']
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
   'Q' : ["TIME",   "dDmy"],
   'Y' : ["TIME",   "dDmy"],

   'E' : ["USER",   "eilkco",  "email",        "wuser"],
   'I' : ["USER",   "eilkco",  "fstname",      "wuser"],
   'L' : ["USER",   "eilkco",  "lstname",      "wuser"],
   'K' : ["USER",   "eilkco",  "org_name",     "wuser"],
   'O' : ["USER",   "eilkco",  "org_type",     "wuser"],
   'N' : ["USER",   "eilkco",  "country",      "wuser"],

   'F' : ["FILE",   "fFStT", "wfile",         "wfile"],
   'G' : ["FILE",   "fFStT", "tindex",        "wfile"],
   'R' : ["FILE",   "fFStT", "search.datasets.title", "search.datasets"],
   'P' : ["FILE",   "fFStT", "specialist",    "dsowner"],

   'W' : ["METHOD", "M",      "method",       "wusage"],
}

# valid options for %params, a hash array of command line parameters
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
#   h -- for give emails, include their histical emails registered before
#   H -- a string of report title to replace the default one
#   i -- array of specified first names
#   I -- use given email IDs for email notice of data update
#   k -- array of specified orginization names
#   l -- array of specified last names
#   L -- column delimiter for output
#   m -- array of specified months 
#   M -- array of specified download methods 
#   N -- number read range, arrage of 1 or 2 integers
#   o -- array of specified orginization types
#   O -- a string of short field names for sorting on
#   q -- array of the specified quarters, normally combined with years
#   S -- array of login names of specialists who own the datasets
#   t -- array of specified dataset names
#   T -- dataset range, array of 1 or 2 dataset names
#   U -- use given unit for file or data sizes
#   v -- array of specified IP addresses
#   V -- IP address range
#   w -- generate view without totals
#   y -- array of specified years
#   z -- generate view including entries with zero usage
params = {}

# relationship between parameter options and short field names, A option is not
# related to a field name if it is not in keys %SNS 
SNS = {
   'c' : 'N', 'd' : 'D', 'D' : 'D', 'e' : 'E', 'f' : 'F', 'F' : 'F', 'i' : 'I',
   'k' : 'K', 'l' : 'L', 'm' : 'M', 'M' : 'W', 'N' : 'H', 'o' : 'O', 'q' : 'Q',
   'S' : 'P', 't' : 'T', 'T' : 'T', 'v' : 'V', 'V' : 'V', 'y' : 'Y'
}

tablenames = fieldnames = condition = ''
sfields = []
gfields = []
dfields = []
pgname = 'viewwebusage'
DSID = None

#
# main function to run this program
#
def main():

   PgDBI.view_dbinfo()
   argv = sys.argv[1:]
   inputs = []
   option = 'C'   # default option

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
         if val != '!':
            if option == 's':
               val = int(val)*1000000    # convert MBytes to Bytes
            elif option in SNS:
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
   
   if 'o' not in params:
      if 'e' not in params:
         params['o'] = ['!', "'DSS'"]   # default to exclude 'DSS' for organization
   elif params['o'][0] == "'ALL'":
      del params['o']

   usgtable = "wusage"
   years = PgView.build_year_list(params, VUSG)
   build_query_strings(usgtable)  # build tablenames, fieldnames, and conditions
   records = None
   if DSID:
      global tablenames, condition
      wname = "wfile_" + DSID
      tablenames = tablenames.replace('wfile', wname)
      condition = condition.replace('wfile', wname)
   for year in sorted(years):
      tname = "{}_{}".format(usgtable, year)
      tbls = tablenames.replace(usgtable, tname)
      flds = fieldnames.replace(usgtable, tname)
      cond = condition.replace(usgtable, tname)
      pgrecs = PgDBI.pgmget(tbls, flds, cond, PgLOG.UCLWEX)
      if pgrecs:
         if records:
            for fld in records: records[fld].extend(pgrecs[fld])
         else:
            records = pgrecs
   if not records: PgLOG.pglog("No Usage Found For Given Conditions", PgLOG.LGWNEX)
   totals = None if 'w' in params else {}
   if dfields or totals != None or len(years) > 1:
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

   cols = params['C'][0] if 'C' in params else 'X'
   if cols == 'X': PgLOG.pglog("{}: miss field names '{}'".format(pgname, VUSG['SNMS']), PgLOG.LGWNEX)

   if cols.find('Q') > -1 and cols.find('Y') < 0:   # add Y if Q included
      cols = re.sub('Q', 'YQ', cols)
      params['C'][0] = cols

   if 'G' in cols:
      global DSID
      multids = False
      if 't' in params and len(params['t']) == 1:
         if '%' in params['t'][0]: multids = True
         DSID = params['t'][0][1:8]
      else:
         multids = True
      if multids:
         PgLOG.pglog(pgname + ": Specify a single dsid for Top Group Usage via option -t", PgLOG.LGWNEX)
      
   for sn in cols:
      if sn == 'X': continue  # do not process INDEX field
      if VUSG['SNMS'].find(sn) < 0:
         PgLOG.pglog("{}: Field {} must be in field names '{}X'".format(pgname, sn, VUSG['SNMS']), PgLOG.LGWNEX)
      if 'z' not in params or sn in EXPAND: continue
      fld = FLDS[sn]
      if fld[6] != 'G': continue
      PgLOG.pglog("{}: cannot show zero usage for unexpandable field {} - {}".formt(pgname, sn, fld[0]), PgLOG.LGWNEX)

   if 'E' in params or 'I' in params:
      if 'z' in params:
         PgLOG.pglog(pgname + ": option -z and -E/-I can not be present at the same time", PgLOG.LGWNEX)
      elif 't' not in params or len(params['t']) > 1:
         PgLOG.pglog(pgname + ": specify one dataset for viewing usage of notified users", PgLOG.LGWNEX)
      elif 'E' in params and 'I' in params:
         PgLOG.pglog(pgname + ": option -E and -I can not be present at the same time", PgLOG.LGWNEX)

   for opt in params:
      if VUSG['CNDS'].find(opt) > -1: return
   PgLOG.pglog("{}: miss condition options '{}'".format(pgname, VUSG['CNDS']), PgLOG.LGWNEX)

#
# process parameter options to build all query strings
# global variables are used directly and nothing passes in and returns back
#
def build_query_strings(usgtable):

   # initialize query strings
   global condition, fieldnames, tablenames
   joins = having = groupnames = ''
   tablenames = usgtable
   cols = params['C'][0]

   if 'U' in params:    # reset units for file and read sizes
      if cols.find('B') > -1: FLDS['B'] = PgView.set_data_unit(FLDS['B'], params['U'][0], "sum(size_read)")
      if cols.find('S') > -1: FLDS['S'] = PgView.set_data_unit(FLDS['S'], params['U'][0], "data_size")

   if 'e' in params and 'h' in params: params['e'] = PgView.include_historic_emails(params['e'], 2)

   for opt in params:
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
         if VUSG['NOPT'].find(opt) > -1: continue
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
   if 'E' in params or 'I' in params:
      (tablenames, joins) = PgView.join_query_tables("emreceive", tablenames, joins, usgtable)
   if joins:
      if condition:
         condition = "{} AND {}".format(joins, condition)
      else:
         condition = joins
   if 'E' in params or 'I' in params:
      condition += PgView.notice_condition(params['E'], None, params['t'][0])
   if groupnames and sfields: condition += " GROUP BY " + groupnames
   if having: condition += " HAVING " + having


def expand_records(records):

   recs = PgView.expand_query("TIME", records, params, EXPAND)

   trecs = PgView.expand_query("USER", records, params, EXPAND, VUSG, SNS, FLDS)
   recs = PgUtil.crosshash(recs, trecs)

   trecs = PgView.expand_query("FILE", records, params, EXPAND, VUSG, SNS, FLDS)
   recs = PgUtil.crosshash(recs, trecs)

   trecs = PgView.expand_query("METHOD", records, params, EXPAND, VUSG, SNS, FLDS)
   recs = PgUtil.crosshash(recs, trecs)

   return PgUtil.joinhash(records, recs, 0, 1)

#
# call main() to start program
#
if __name__ == "__main__": main()
