#
###############################################################################
#
#     Title : PgView.py
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 09/24/2020
#             2025-03-27 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-database.git
#   Purpose : python library module to help rountinely updates of new data 
#             for one or multiple datasets
#
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
###############################################################################
#
import os
import re
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgDBI

#
# simple_output(params: reference to parameter hush array
#                 flds: reference to field hush array
#              records: PgSQL query result)
# generate a simple view without header and page information by using the passed in PgSQL query result
#
def simple_output(params, flds, records, totals = None):

   cols = params['C'][0]
   ccnt = len(cols)        # get output dimensions
   sep = params['L'][0] if 'L' in params else '  '
   slen = len(sep)

   # get total line length, dynamically evaluating column lengthes if column 4 in %FLDS is zero
   rcnt = linelen = 0
   if 'A' in params: rcnt = int(params['A'][0])
   for i in range(ccnt):
      if not (rcnt or cols[i] == 'X'): rcnt = len(records[cols[i]])
      fld = flds[cols[i]]
      if not fld[4]: fld[4] = PgUtil.get_column_length(fld[0], records[cols[i]])
      if linelen: linelen += slen
      linelen += abs(fld[4])

   # print position numbers for reference of read
   nstr = '123456789'
   nline = ''
   for i in range(0,linelen,10):
      nline += str(int(i/10)%10)
      if (linelen-i) < 10:
         nline += nstr[0:(linelen-i-1)]
      else:
         nline += nstr
   print(nline)

   # print column titles
   tline = ''
   for i in range(ccnt):
      if i: tline += sep    # delimiter to separate columns
      fld = flds[cols[i]]
      if fld[4] < 0 or fld[5] > 0:   # right justify
         tline += "{:>{}}".format(fld[0], abs(fld[4]))
      else:    # left justify
         tline += "{:{}}".format(fld[0], abs(fld[4]))
   print(tline)
 
   # print result now
   for j in range(rcnt):
      sline = ''
      for i in range(ccnt):
         fld = flds[cols[i]]
         if cols[i] == 'X':
            val = j+1
         else:
            val = records[cols[i]][j]
            if val is None:
               if fld[4] < 0 or fld[5] > 0:
                  val = 0
               else:
                  val = ' '
         if i > 0: sline += sep   # delimiter to separate columns
         if fld[5] > 0:           # right justify, numeric field with precision
            sline += "{:{}.{}f}".format(abs(val), fld[4], fld[5])
         elif fld[4] < 0:         # right justify, negative field size
            sline += "{:>{}}".format(str(val), -fld[4])
         elif i < (ccnt-1):     # left justify, normal display with trailing spaces
            sline += "{:{}.{}}".format(str(val), fld[4], fld[4])
         else:                    # normal display w/o trailing spaces
            sline += str(val)
      print(sline)
   
   if totals:
      print(''.join(['-']*linelen))
      sline = ''
      for i in range(ccnt):
         if i > 0: sline += sep   # delimiter to separate columns
         fld = flds[cols[i]]
         if cols[i] == 'X':
            sline += "{:{}}".format('TOTAL', abs(fld[4]))
            continue
         val = totals[cols[i]]
         if val is None:
            sline += "{:{}}".format(' ', abs(fld[4]))
            continue

         if fld[5] > 0:           # right justify, numeric field with precision
            sline += "{:{}.{}f}".format(abs(val), fld[4], fld[5])
         elif fld[4] < 0:         # right justify, negative field size
            sline += "{:>{}}".format(str(val), -fld[4])
         elif i < (ccnt-1):     # left justify, normal display with trailing spaces
            sline += "{:{}}".format(str(val), abs(fld[4]))
         else:                    # normal display w/o trailing spaces
            sline += str(val)
      print(sline)
      

#
# set_data_unit(fld: reference to original array of size field
#              unit: given unit to show data size, 'BKMGTP'
#             fname: the field name in RDADB, in form of SUM() if needed)
#
# change unit of data size and reset field length according to given data unit
#
def set_data_unit(fld, unit, fname, origin = 0):
   
   factor = {'B' : 1, 'K' : 100, 'M' : 1000000, 'G' : 1000000000,
             'T' : 1000000000000, 'P' : 1000000000000000}

   if unit == 'B':
      if re.match(r'^sum', fname):
         fld[0] = re.sub(r'^MB', 'B', fld[0], 1)
         fld[1] = fname
         fld[4] = -17
         fld[5] = -1
   elif unit == 'M':
      if not re.match(r'^sum', fname):
         fld[0] = re.sub(r'^B', 'MB', fld[0], 1)
   elif unit in factor:
      fld[0] = re.sub(r'^M{0,1}B', unit+'B', fld[0], 1)
   else:
      PgLOG.pglog("{}: Unknown unit must be in ({})".format(unit, ','.join(factor)), PgLOG.LGEREX)

   fact = factor[unit]      
   reverse = 0
   if origin:
      if fact >= origin:
         fact /= origin
      else:
         fact = origin/fact
         reverse = 1

   if fact > 1:
      fld[1] = "round({}{}{}, 4)".format(fname, '*' if reverse else '/', fact)
      fld[4] = -14
      fld[5] = 3

   return fld

#
# get all available date(D)/month(M)/year(Y) for given conditions of
# of dates, daterange, months or years
#
def expand_time(exps, records, params, expand):

   get = 0
   opts = aold = aqtr = None
   for opt in exps:
      if opt == "D":
         get |= 1
         if 'D' in records: aold = records['D']
         opts = expand['D'][1]
      elif opt == "M":
         get |= 2
         if not aold and 'M' in records: aold = records['M']
         if not opts: opts = expand['M'][1]
      elif opt == "Y":
         get |= 4
         if not aold and 'Y' in records: aold = records['Y']
         if not opts: opts = expand['Y'][1]
      elif opt == "Q":
         get |= 8
         if 'Q' in records: aqtr = records['Q']
         if not opts: opts = expand['Q'][1]
   cqtr = 0
   qcond = cond = None
   for opt in opts:
      if opt in params:
         if opt == 'q':
            qcond = params[opt]
            cqtr = len(qcond)
         elif not cond:
            cond = params[opt]
            break
   
   if qcond and not cond:
      PgLOG.pglog("no zero usage on temporal condition of quarter only", PgLOG.LGWNEX)

   anew = []
   if cond:
      if opt == 'd':
         anew = cond
      elif opt == 'D':
         (start, end) = PgUtil.daterange(cond[0], cond[1])
         if not (end and start):
            PgLOG.pglog("Must specify valid start and end dates", PgLOG.LGWNEX)
         dy = dm = dd = 0
         if get&1:
            dd = 1
         elif get&10:
            dm = 1
         else:
            dy = 1
         date = start
         anew.append(date)
         while date < end:
            date = PgUtil.adddate(date, dy, dm, dd)
            anew.append(date)
      elif opt == 'm':
         if (get&1) == 0:
            anew = cond
         else:
            for month in cond:
               for i in range(1, 29):
                  anew.append("{}-{:02}".format(month, i))
               date = anew[27]
               end = PgUtil.enddate(date, 0, 'M')
               while date < end:
                  date = PgUtil.adddate(date, 0, 0, 1)
                  anew.append(date)
      elif opt == 'y':
         if (get&4) == 4:
            anew = cond
         else:
            for year in cond:
               for j in range(1, 13):
                  month = "{}={:02}".format(year, j)
                  if qcond:
                     qtr = int(j/3) + 1
                     i = 0
                     while i < cqtr:
                        if qcond[i] == qtr: break
                        i += 1
                     if i > cqtr: continue   # skip month not in included quarters
                  if get&1:
                     for i in range(1, 29):
                        anew.append("{}-{:02}".format(month, i))
                     date = anew[27]
                     end = PgUtil.enddate(date, 0, 'M')
                     while date < end:
                        date = PgUtil.adddate(date, 0, 0, 1)
                        anew.append(date)
                  else:
                     anew.append(month)
   elif records:
      anew = aold

   cnew = len(anew)
   aret = []
   for j in range(cnew):
      date = anew[j]
      if get&1 == 0:
         if get&2:  #get month
            ms = re.match(r'^(\d\d\d\d-\d\d)', date)
            if ms: date = ms.group(1)
         elif get&4:  #get year
            ms = re.match(r'^(\d\d\d\d)-(\d+)', date)
            if ms:
               date = ms.group(1)
               mn = int(ms.group(2))
               if get&8:
                  qtr = mn - ((mn - 1)%3)  #first month of quarter
                  date = "{}-{}".format(date, qtr)
            else:
               ms = re.match(r'^(\d\d\d\d)', date)
               if ms:
                  date = ms.group(1)
                  if get&8 and aqtr:
                     qtr = 3*(aqtr[j]-1) + 1  #first month of quarter
                     date = "{}-{}".format(date, qtr)

      if date not in aret:
         aret.append(date)

   rets = {}
   for date in aret:
      if get&1:
         if 'D' not in rets: rets['D'] = []
         rets['D'].append(date)
      if get&2:
         ms = re.match(r'^(\d\d\d\d-\d\d)', date)
         if ms:
            if 'M' not in rets: rets['M'] = []
            rets['M'].append(ms.group(1))
      if get&4:
         ms = re.match(r'^(\d\d\d\d)', date)
         if ms:
            if 'Y' not in rets: rets['Y'] = []
            rets['Y'].append(ms.group(1))
      if get&8:
         ms = re.match(r'^\d\d\d\d-(\d+)', date)
         if ms:
            if 'Q' not in rets: rets['Q'] = []
            rets['Q'].append((int((int(ms.group(1)) - 1)/3) + 1))
   
   return rets

#
# the detail query action for expand_query()
#
def query_action(exps, records, expand, tables, cond):
   
   fields = ''
   for exp in exps:
      fields += ", " if fields else "DISTINCT "
      fields += "{} {}".format(expand[exp][2], exp)
   pgrecs = PgDBI.pgmget(tables, fields, cond, PgLOG.UCLWEX)
   cnew = PgUtil.hashcount(pgrecs, 1)
   cexp = len(exps)
   cret = 0
   rets = {}
   for i in range(cnew):
      j = 0
      while j < cret:
         k = 0
         while k < cexp:
            exp = exps[k]
            if PgUtil.pgcmp(pgrecs[exp][i], rets[exp][j]): break
         if k >= cexp: break

      if j >= cret:
         for k in range(cexp):
            exp = exps[k]
            if exp not in rets: rets[exp] = []
            rets[exp].append(pgrecs[exp][i])
         cret += 1

   return rets

#
#  build table name and join condition strings
#
def join_query_tables(tblname, tablenames = '', joins = '', tbljoin = ''):

   if not tablenames:
      return (tblname, "")
   elif tablenames.find(tblname) > -1:
      return (tablenames, joins)
   
   if not tbljoin: tbljoin = tablenames.split(', ')[0]
   cndstr = ''
   jfield = 'dsid'
   fmtstr = "{}.{} = {}.{}"
   if tblname == 'gofile':
      jfield = 'task_id'
   elif tblname == 'wfile':
      jfield = 'wid'
   elif tblname == 'user':
      jfield = 'uid'
   elif tblname == 'emreceive':
      jfield = 'email'
      if tbljoin == 'wusage':
         (tablenames, joins) = join_query_tables('wuser', tablenames, joins, tbljoin)
         tbljoin = 'wuser'
   elif tblname == 'ruser':
      jfield = 'email'
      if tbljoin == 'gotask': cndstr = " AND rdate <= DATE(completion_time) AND (end_date IS NULL OR end_date >= DATE(completion_time))"
   elif tblname == 'wuser':
      jfield = 'wuid'
      if tbljoin == 'wusage':
         fmtstr = "{}.{}_read = {}.{}"
      else:
         fmtstr = "{}.{}_request = {}.{}"
   elif tblname == 'search.datasets':
      if not PgLOG.PGLOG['NEWDSID']: fmtstr = "substring({}.{}, 3) = {}.{}"
      if tbljoin == 'gotask':
         (tablenames, joins) = join_query_tables('gofile', tablenames, joins, tbljoin)
         tbljoin = 'gofile'
   elif tblname == 'dsowner':
      cndstr = " AND priority = 1"
      if tbljoin == 'gotask':
         (tablenames, joins) = join_query_tables('gofile', tablenames, joins, tbljoin)
         tbljoin = 'gofile'
   elif tblname == 'wfpurge':
      jfield = 'index'

   tablenames += ', ' + tblname   # add to table name string
   if joins: joins += " AND "
   joins += fmtstr.format(tbljoin, jfield, tblname, jfield) + cndstr

   return (tablenames, joins)

#
# expand reocrds via query action
#
def expand_query(expid, records, params, expand, vusg = None, sns = None, flds = None):
   
   cols = params['C'][0]
   exps = []
   # gather the valid expands
   for opt in expand:
      fld = expand[opt]
      if not (fld[0] == expid and cols.find(opt) > -1): continue
      exps.append(opt)

   if not exps: return None
   if expid == "TIME": return expand_time(exps, records, params, expand)

   # check and join tables
   tables = joins = ''
   for opt in exps:
      fld = expand[opt]
      (tables, joins) = join_query_tables(fld[3], tables, joins)

   cond = ""
   opts = expand[exps[0]][1]
   for opt in opts:
      if opt not in params: continue
      sn = sns[opt]
      fld = expand[sn] if sn in expand else flds[sn]
      cond = get_view_condition(opt, sn, fld, params, vusg, cond)
      (tables, joins) = join_query_tables(fld[3], tables, joins)

   if joins and cond:
      cond = "{} AND {}".format(joins, cond)
   elif joins:
      cond = joins

   return query_action(exps, records, expand, tables, cond)

#
# build year list for yearly tables for given temporal conditions
#
def build_year_list(params, vusg):

   yrs = []
   
   tcnd = vusg['TCND'] if 'TCND' in vusg else []
   rcnd = vusg['RCND'] if 'RCND' in vusg else []
   for opt in tcnd:
      if opt in params and params[opt]:
         svals = params[opt]
         lens = len(svals)
         vals = [0]*lens
         for i in range(lens):
            ms = re.match(r"^'*(\d\d\d\d)", svals[i])
            if ms: vals[i] = int(ms.group(1))
         if opt in rcnd:
            if lens == 1: vals.append(0)
            if not vals[0]: vals[0] = 2004
            if not vals[1]: vals[1] = int(PgUtil.curdate('YYYY'))
            for yr in range(vals[0], vals[1]+1):
               if yr not in yrs: yrs.append(yr)
         else:
            for yr in vals:
               if yr and yr not in yrs: yrs.append(yr)

   return yrs

#
#evaluate daterange, remove/add quotes as needed; add time ranges on if dt is True
#
def evaluate_daterange(dates, dr, dt):

   if dates[0]:
      ms = re.match(r"^'(\w.+\w)'$", dates[0])
      if ms: dates[0] = ms.group(1)
   if dates[1]:
      ms = re.match(r"^'(\w.+\w)'$", dates[1])
      if ms: dates[1] = ms.group(1)
   if dr: dates = PgUtil.daterange(dates[0], dates[1])
   if dt: dates = PgUtil.dtrange(dates)
   if dates[0]: dates[0] = "'{}'".format(dates[0])
   if dates[1]: dates[1] = "'{}'".format(dates[1])

   return dates

#
# get view condition
#
def get_view_condition(opt, sn, fld, params, vusg, cond = ''):

   cols = params['C'][0]
   if 'HCND' in vusg and vusg['HCND'].find(opt) > -1 and cols.find(sn) < 0:
      PgLOG.pglog("{}-{} Must be in FieldList: {} for Option -{}".format(sn, fld[0], cols, opt), PgLOG.LGWNEX)

   dt = True if 'TOPT' in vusg and opt in vusg['TOPT'] else False
   inputs = params[opt]
   if inputs[0] == '!':
      negative = 1
      inputs.pop(0)
   else:
      negative = 0
   vcond = ''
   if 'RCND' in vusg and vusg['RCND'].find(opt) > -1:  #build condition string for range options
      if len(inputs) == 1: inputs.append('')
      if opt == 'D': inputs = evaluate_daterange(inputs, True, dt)
      if inputs[0] and inputs[1]:
         if negative: vcond += 'NOT '
         vcond += "BETWEEN {} AND {}".format(inputs[0], inputs[1])
      elif inputs[0]:
         vcond = "{} {}".format('<' if negative else '>=', inputs[0])
      elif inputs[1]:
         vcond = "{} {}".format('>' if negative else '<=', inputs[1])
   elif 'ACND' in vusg and vusg['ACND'].find(opt) > -1:  #condition string for array options
      for input in inputs:
         if vcond: vcond += " {} {} ".format((" AND" if negative else " OR"), fld[2])
         if 'ECND' in vusg and vusg['ECND'].find(opt) > -1:
            if opt in 'mMyY': # year/month entered
               if negative: vcond += 'NOT '
               dates = evaluate_daterange([input, input], True, dt)
               vcond += "BETWEEN {} AND {}".format(dates[0], dates[1])
            elif opt in 'dD' and dt: # date entered
               if negative: vcond += 'NOT '
               dates = evaluate_daterange([input, input], False, dt)
               vcond += "BETWEEN {} AND {}".format(dates[0], dates[1])
            else:
               PgLOG.pglog("-{}: NOT evaluable condition option".format(opt), PgLOG.LGEREX)
         elif 'SFLD' in vusg and vusg['SFLD'].find(sn) > -1 and re.search(r'[%_]', input):
            if negative: vcond += 'NOT '
            vcond += "LIKE " + input
         else:
            vcond += "{} {}".format('<>' if negative else '=', input)
   if vcond:
      if cond: cond += " AND "
      cond += "({} {})".format(fld[2], vcond)

   return cond

#
# reorder expanded result
#
def order_records(recs, oflds, cnt = 0):

   if not cnt: cnt = PgUtil.hashcount(recs, 1)   
   if cnt < 2 or not oflds: return recs

   oary = []
   dary = []
   for oname in oflds:
      uname = oname.upper()
      if oname == uname:
         desc = 1
      else:
         desc = -1
      if uname in recs:
         oary.append(uname)
         dary.append(desc)
   if not oary: return recs

   srecs = [None]*cnt
   ocnt = len(oary)
   for i in range(cnt):
      srecs[i] = [None]*(ocnt+1)
      for j in range(ocnt):
         srecs[i][j] = recs[oary[j]][i]
      srecs[i][ocnt] = i
   
   srecs = PgUtil.quicksort(srecs, 0, cnt-1, dary, ocnt)
   
   # reset order of records according reordered srecs{}
   rets = {}
   for oname in recs:
      rets[oname] = [None]*cnt
      for i in range(cnt):
         j = srecs[i][ocnt]
         rets[oname][i] = recs[oname][j]
   
   return rets

#
# for given country info to get long country name
#
def get_country_name(cid):

   if not cid or len(cid) != 2: return cid
   pgrec = PgDBI.pgget("countries", "token", "domain_id = '{}'".format(cid), PgLOG.LGEREX)

   return (pgrec['token'] if pgrec else cid)

#
# get group index array from given group IDs and dataset IDs
#
def get_group_indices(grpids, dsids, indices):

   cnd = PgDBI.get_field_condition("grpid", grpids, 1, 1)
   if dsids: cnd += PgDBI.get_field_condition("dsid", dsids, 1)
   if indices: cnd += PgDBI.get_field_condition("gindex", indices, 1)
   pgrecs = PgDBI.pgmget("dsgroup", "DISTINCT gindex", cnd, PgLOG.LGEREX)

   return (pgrecs['gindex'] if pgrecs else None)

#
#  expand groups to include IDs or titles or both
#
def expand_groups(indices, dsids, igid, ititle):

   if not indices: return None
   count = len(indices)

   sindices = []
   for i in range(count):
      sindices.append("{}".format(indices[i]))
      if indices[i]:
         pgrec = PgDBI.pgget("dsgroup", "grpid, title", "dsid = '{}' AND gindex = {}".format(dsids[i], indices[i]), PgLOG.LGEREX)
         if not pgrec: continue
         if igid and pgrec['grpid']: sindices[i] += "-" . pgrec['grpid']
         if ititle and pgrec['title']: sindices[i] += "-" . pgrec['title']
      else:
         if igid: sindices[i] += "-DATASET"
         if ititle: sindices[i] += "-The WHOLE DATASET"

   return sindices

#
# create condition for emails of users being notified for data updates
#
def notice_condition(dates, emids, dsid):

   cond = "dsid = '{}' AND ".format(dsid)
   count = len(emids) if emids else 0
   if count > 0:
      if count == 1:
         cond += "emid = " + emids[0]
      else:
         cond += "emid IN ("
         for i in range(count):
            if i > 0: cond += ", "
            cond += emids[i]
         cond += ")"
   else:
      count = len(dates) if dates else 0
      if count == 1:
         cond += " AND date >= '{}'".format(dates[0])
      else:
         cond += " AND date BETWEEN '{}' AND '{}'".format(dates[0], dates[1])
   pgrecs = PgDBI.pgmget("emnotice", "emid", cond,  PgDBI.PGDBI['LOGACT']|PgLOG.EXITLG)
   count = len(pgrecs['emid']) if pgrecs else 0
   if count > 0:
      emids = pgrecs['emid']
   else:
      PgLOG.pglog("Not Email Notice sent for " + cond, PgDBI.PGDBI['LOGACT']|PgLOG.EXITLG)
   
   cond = " AND emreceive.emid "
   if count == 1:
      cond += "= " + emids[0]
   else:
      cond += "IN ("
      for i in range(count):
         if i > 0: cond += ", "
         cond += emids[i]
      cond += ")"

   return cond

#
# get email list including historical ones
#
def include_historic_emails(emails, opt):

   elist = {}
   if not opt: opt = 3

   for email in emails:
      elist[email] = 1
      if opt&1:
         pgrec = PgDBI.pgget("user", "userno", "email = '{}'".format(email), PgLOG.LGEREX)
         if pgrec and pgrec['userno']:
            pgrecs = PgDBI.pgmget("user", "email", "userno = {} AND email <> '{}'".format(pgrec['userno'], email), PgLOG.LGEREX)
            if pgrecs:
               for em in pgrecs['email']:
                  elist[em] = 1
      if opt&2:
         pgrec = PgDBI.pgget("ruser", "id", "email = '{}'".format(email), PgLOG.LGEREX)
         if pgrec and pgrec['id']:
            pgrecs = PgDBI.pgmget("ruser", "email", "id = {} AND email <> '{}'".format(pgrec['id'], email), PgLOG.LGEREX)
            if pgrecs:
               for em in pgrecs['email']:
                  elist[em] = 1
   
   emails = list(elist)
   
   return emails

#
# combine two query dicts
#
def combine_hash(adict, bdict, gflds, sflds):
   
   if not bdict: return adict
   if not adict: return bdict
   for fld in adict: adict[fld].extend(bdict[fld])
   if not gflds: return adict
   adict = order_records(adict, gflds)
   acnt = len(adict[gflds[0]])
   b = 0
   a = b+1
   while a < acnt:
      gsame = 1
      for fld in gflds:
         if adict[fld][a] != adict[fld][b]:
            gsame = 0
            break
      if gsame:  # same group records
         for fld in sflds: 
            adict[fld][b] += adict[fld][a]
            del adict[fld][a]
         for fld in gflds:
            del adict[fld][a]
         acnt -= 1
      b = a
      a = b+1

   return adict

#
# compact a dict by group fields to get distinct count and total sum 
#
def compact_hash_groups(adict, gflds, sflds, dflds, totals):

   bdict = {}
   ddict = {}
   tdict = {}
   acnt = PgUtil.hashcount(adict, 1)
   if gflds: adict = order_records(adict, gflds, acnt)
   for fld in dflds:
      bdict[fld] = [0]
      ddict[fld] = {adict[fld][0] : None}
   for fld in sflds:
      bdict[fld] = [adict[fld][0]]
   for fld in gflds:
      bdict[fld] = [adict[fld][0]]

   if totals != None:
      for fld in dflds:
         totals[fld] = 0
         tdict[fld] = {}
      for fld in sflds:
         totals[fld] = 0
      for fld in gflds:
         totals[fld] = None

   p = b = 0
   a = 1
   while a < acnt:
      gsame = True
      for fld in gflds:
         if adict[fld][a] != adict[fld][p]:
            gsame = False
            break
      if gsame:  # same group records
         for fld in sflds:
            if adict[fld][a]: bdict[fld][b] += adict[fld][a]
         for fld in dflds:
            ddict[fld][adict[fld][a]] = None
      else:
         for fld in dflds:
            if totals:
               for dkey in ddict[fld]:
                  tdict[fld][dkey] = None
            bdict[fld][b] = len(ddict[fld])
            bdict[fld].append(0)
            ddict[fld] = {adict[fld][a] : None}
         for fld in sflds:
            if totals: totals[fld] += bdict[fld][b]
            bdict[fld].append(adict[fld][a])
         for fld in gflds:
            bdict[fld].append(adict[fld][a])
         b += 1
      p = a
      a += 1

   if totals:
      for fld in dflds:
         for dkey in ddict[fld]:
            tdict[fld][dkey] = None
         totals[fld] = len(tdict[fld])
      for fld in sflds:
         totals[fld] += bdict[fld][b]
   for fld in dflds:
      bdict[fld][b] = len(ddict[fld])

   return bdict
