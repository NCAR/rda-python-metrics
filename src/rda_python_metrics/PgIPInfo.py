#
###############################################################################
#
#     Title : PgIPInfo
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 08/22/2023
#            2025-03-26 transferred to package rda_python_metrics from
#            https://github.com/NCAR/rda-shared-library.git
#   Purpose : python module to retrieve ip info from ipinfo
#             or geoip2 modules
# 
#    Github : https://github.com/NCAR/rda-python-common.git
#
###############################################################################
#
import geoip2.database as geodb
import ipinfo
import socket
from rda_python_common import PgLOG
from rda_python_common import PgDBI
from rda_python_common import PgUtil

IPINFO = {
   'TOKEN' : 'b2a67fdd1a9ba3',
   'DBFILE' : PgLOG.PGLOG['DSSHOME'] + '/dssdb/GeoLite2-City.mmdb',
   'CDATE' : PgUtil.curdate(),
   'IPUPDT' : 0,
   'IPADD'  : 0
}

IPDB = None
G2DB = None
IPRECS = {}
COUNTRIES = {}

#
# Get country token name for given two-character domain id
#
def get_country_name_code(dm):
   
   if dm not in COUNTRIES:
      pgrec = PgDBI.pgget('countries', 'token', "domain_id = '{}'".format(dm))
      COUNTRIES[dm] = pgrec['token'] if pgrec else 'Unknown'
   return COUNTRIES[dm]

def get_country_record_code(cname, kname = None):

   name = cname[kname] if kname else cname
   name = name.replace(' ', '.').upper() if name else 'UNITED.STATES'
   if name == 'CHINA': name = 'P.R.CHINA'

   return name

def set_ipinfo_database():

   global IPDB
   try:
      IPDB = ipinfo.getHandler(IPINFO['TOKEN'])
   except Exception as e:
      PgLOG.pglog('ipinfo: ' + str(e), PgLOG.LGEREX)

#
# get a ipinfo record for given ip address
#
def get_ipinfo_record(ip):

   if not IPDB: set_ipinfo_database()
   try:
      iprec = IPDB.getDetails(ip).all
      if 'hostname' not in iprec:
         PgLOG.pglog("ipinfo: {} - ip address is not in the database".format(ip), PgLOG.LOGERR)
         return None
   except Exception as e:
      PgLOG.pglog("ipinfo: {} - {}".format(ip, str(e)), PgLOG.LOGWRN)
      return None
      
   record = {'ip' : ip, 'stat_flag' : 'A', 'hostname' : ip}
   if 'hostname' in iprec:
      record['hostname'] = iprec['hostname']
      record['org_type'] = PgDBI.get_org_type(None, record['hostname'])
   record['lat'] = float(iprec['latitude']) if iprec['latitude'] else 0
   record['lon'] = float(iprec['longitude']) if iprec['longitude'] else 0
   if 'org' in iprec: record['org_name'] = iprec['org']
   record['country'] = get_country_record_code(iprec, 'country_name')
   if 'city' in iprec: record['city'] = PgLOG.convert_chars(iprec['city'])
   if 'postal' in iprec: record['postal'] =  iprec['postal']
   record['timezone'] = iprec['timezone']

   return record

def set_geoip2_database():

   global G2DB   
   try:
      G2DB = geodb.Reader(IPINFO['DBFILE'])
   except Exception as e:
      PgLOG.pglog("geoip2: " + str(e), PgLOG.LGEREX)

#
# get a geoip2 record for given ip address
#
def get_geoip2_record(ip):

   if not G2DB: set_geoip2_database()
   try:
      city = G2DB.city(ip)
   except Exception as e:
      PgLOG.pglog("geoip2: {} - {}".format(ip, str(e)), PgLOG.LOGWRN)
      return None

   record = {'ip' : ip, 'stat_flag' : 'M'}
   record['lat'] = float(city.location.latitude) if city.location.latitude else 0
   record['lon'] = float(city.location.longitude) if city.location.longitude else 0
   record['country'] = get_country_name_code(city.country.name)
   record['city'] = PgLOG.convert_chars(city.city.name)
   record['postal'] =  city.postal.code
   record['timezone'] = city.location.time_zone
   record['hostname'] = ip
   record['org_type'] = '-'

   try:
      hostrec = socket.gethostbyaddr(ip)
   except Exception as e:
      PgLOG.pglog("socket: {} - {}".format(ip, str(e)), PgLOG.LOGWRN)
      return record
   record['hostname'] = hostrec[1][0] if hostrec[1] else hostrec[0]
   record['org_type'] = PgDBI.get_org_type(None, record['hostname'])

   return record

#
# update wuser.email for hostname changed
#
def update_wuser_email(nhost, ohost):

   pgrec = PgDBI.pgget('wuser', 'widx', "email = 'unknown@{}'".format(ohost))
   if pgrec: PgDBI.pgexec("UPDATE wuser SET email = 'unknown@{}' WHERE widx = {}".format(nhost, pgrec['widx']))

#
# update a ipinfo record; add a new one if not exists yet
#
def update_ipinfo_record(record, pgrec = None):

   tname = 'ipinfo'
   cnd = "ip = '{}'".format(record['ip'])
   if not pgrec: pgrec = PgDBI.pgget(tname, '*', cnd)
   if pgrec:
      nrec = get_update_record(record, pgrec)
      if 'hostname' in nrec: update_wuser_email(nrec['hostname'], pgrec['hostname'])
      ret = PgDBI.pgupdt(tname, nrec, cnd) if nrec else 0
      IPINFO['IPUPDT'] += ret
   else:
      record['adddate'] = IPINFO['CDATE']
      ret = PgDBI.pgadd(tname, record)
      IPINFO['IPADD'] += ret

   return ret

#
# set ip info into table ipinfo from python module ipinfo
# if ipopt is True; otherwise, use module geoip2 
#
def set_ipinfo(ip, ipopt = False):

   if ip in IPRECS:
      pgrec = IPRECS[ip]
      if not pgrec or not ipopt or pgrec['stat_flag'] == 'A': return pgrec
   else:
      pgrec = PgDBI.pgget('ipinfo', '*', "ip = '{}'".format(ip))

   if not pgrec or ipopt and pgrec['stat_flag'] == 'M':
      record = None if ipopt else get_geoip2_record(ip)
      if not (record and 'hostname' in record): record = get_ipinfo_record(ip)
      if record and update_ipinfo_record(record, pgrec): pgrec = record
   
   IPRECS[ip] = pgrec
   return pgrec

#
# compare and return a new record holding fields with different values only
#
def get_update_record(nrec, orec):

   record = {}   
   for fld in nrec:
      if nrec[fld] != orec[fld]:
         record[fld] = nrec[fld]
   return record
