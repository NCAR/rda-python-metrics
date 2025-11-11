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
import re
import geoip2.database as geodb
import ipinfo
import socket
import dns.resolver
import json
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

GIP = '0.0.0.0'
IPDNS = None
IPDB = None
G2DB = None
IPRECS = {}
COUNTRIES = {}

#
# get save a global dns.resolver.Resolver object
#
def get_dns_resolver(forceget = False):

   global IPDNS

   if forceget or not IPDNS: IPDNS = dns.resolver.Resolver()
   
   return IPDNS

#
# Resolve a domain name to an IP address (A record)
#
def dns_to_ip(dmname, type = 'A'):
   
   ipdns = get_dns_resolver()

   try:
      answers = ipdns.resolve(dmname, type)
      return [str(rdata) for rdata in answers]
   except dns.resolver.NXDOMAIN:
      PgLOG.pglog(f"{dmname}: the domain name does not exist", PgLOG.LOGERR)
   except dns.resolver.Timeout:
      PgLOG.pglog(f"{dmname}: the domain name request timed out", PgLOG.LOGERR)
   except dns.exception.DNSException as e:
      PgLOG.pglog(f"{dmname}: error domain name request: {e}", PgLOG.LOGERR)

   return None

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
# get a ipinfo record for given domain
#
def domain_ipinfo_record(dmname):

   ips = dns_to_ip(dmname)
   
   if ips: return set_ipinfo(ips[0])

   return None

#
# try to get hostname via socket for given ip address
#
def get_ip_hostname(ip, iprec, record):

   record['hostname'] = ip
   if iprec:
      if 'hostname' in iprec and iprec['hostname']:
         record['hostname'] = iprec['hostname']         
         record['org_type'] = PgDBI.get_org_type(None, record['hostname'])
         return
      if 'asn' in iprec and iprec['asn'] and 'domain' in iprec['asn'] and iprec['asn']['domain']:
         record['hostname'] += '.' + iprec['asn']['domain']
         record['org_type'] = PgDBI.get_org_type(None, record['hostname'])
         return

   try:
      hostrec = socket.gethostbyaddr(ip)
      record['hostname'] = hostrec[1][0] if hostrec[1] else hostrec[0]
      record['org_type'] = PgDBI.get_org_type(None, record['hostname'])
   except Exception as e:
      PgLOG.pglog("socket: {} - {}".format(ip, str(e)), PgLOG.LOGWRN)

#
# get a ipinfo record for given ip address
#
def get_ipinfo_record(ip):

   if not IPDB: set_ipinfo_database()
   try:
      iprec = IPDB.getDetails(ip).all
   except Exception as e:
      PgLOG.pglog("ipinfo: {} - {}".format(ip, str(e)), PgLOG.LOGWRN)
      return None

   if 'bogon' in iprec and iprec['bogon']:
      PgLOG.pglog(f"ipinfo: {ip} - bogon, use {GIP}", PgLOG.LOGWRN)
      IPRECS[ip] = PgDBI.pgget('ipinfo', '*', f"ip = '{GIP}'", PgLOG.LGEREX)
      return IPRECS[ip]

   record = {'ip' : ip, 'stat_flag' : 'A', 'hostname' : ip, 'org_type' : '-'}
   get_ip_hostname(ip, iprec, record)
   record['lat'] = float(iprec['latitude']) if iprec['latitude'] else 0
   record['lon'] = float(iprec['longitude']) if iprec['longitude'] else 0
   if 'org' in iprec: record['org_name'] = iprec['org']
   record['country'] = get_country_record_code(iprec, 'country_name')
   record['region'] = PgLOG.convert_chars(iprec['region']) if 'region' in iprec else None
   if 'city' in iprec: record['city'] = PgLOG.convert_chars(iprec['city'])
   if 'postal' in iprec: record['postal'] =  iprec['postal']
   record['timezone'] = iprec['timezone']
   record['ipinfo'] = json.dumps(iprec)

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

   record = {'ip' : ip, 'stat_flag' : 'M', 'org_type' : '-'}
   get_ip_hostname(ip, None, record)
   record['lat'] = float(city.location.latitude) if city.location.latitude else 0
   record['lon'] = float(city.location.longitude) if city.location.longitude else 0
   record['country'] = get_country_name_code(city.country.name)
   record['city'] = PgLOG.convert_chars(city.city.name)
   record['region'] = PgLOG.convert_chars(city.subdivisions.most_specific.name) if city.subdivisions.most_specific.name else None
   record['postal'] =  city.postal.code
   record['timezone'] = city.location.time_zone
   record['ipinfo'] = json.dumps(object_to_dict(city))

   return record

#
# change an object to dict recursively
#
def object_to_dict(obj):
    if hasattr(obj, "__dict__"):
        result = {}
        for key, value in obj.__dict__.items():
            result[key] = object_to_dict(value)
        return result
    elif isinstance(obj, list):
        return [object_to_dict(item) for item in obj]
    else:
        return obj

#
# update wuser.email for hostname changed
#
def update_wuser_email(nhost, ohost):

   pgrec = PgDBI.pgget('wuser', 'wuid', "email = 'unknown@{}'".format(ohost))
   if pgrec: PgDBI.pgexec("UPDATE wuser SET email = 'unknown@{}' WHERE wuid = {}".format(nhost, pgrec['wuid']))

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
def set_ipinfo(ip, ipopt = True):

   if ip in IPRECS: return IPRECS[ip]

   pgrec = PgDBI.pgget('ipinfo', '*', "ip = '{}'".format(ip))
   if not pgrec or ipopt and pgrec['stat_flag'] == 'M':
      record = get_ipinfo_record(ip) if ipopt else None
      if not record: record = get_geoip2_record(ip)
      if record:
         update_ipinfo_record(record, pgrec)
         pgrec = record
   
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

#
# fill the missing info for given ip
#
def get_missing_ipinfo(ip, email = None):

   if not ip:
      if email and '@' in email: ip = dns_to_ip(email.split('@')[1])
      if not ip: return None

   ipinfo = set_ipinfo(ip)
   if ipinfo:
      record = {'org_type' : ipinfo['org_type'],
                'country' : ipinfo['country'],
                'region' : ipinfo['region'],
                'hostname' : ipinfo['hostname'],
                'ip' : ipinfo['ip']}
      if not email or re.search(r'-$', email):
         record['email'] =  'unknown@' + ipinfo['hostname']
      else:
         record['email'] = email
      return record
   else:
      return None


# return wuser record upon success, None otherwise
def get_wuser_record(ip, date, email = None):

   record = get_missing_ipinfo(ip, email)
   if not record: return None

   emcond = "email = '{}'".format(record['email'])
   flds = 'wuid, start_date'   
   pgrec = PgDBI.pgget("wuser", flds, emcond, PgLOG.LOGERR)
   if pgrec:
      record['wuid'] = pgrec['wuid']
      if PgUtil.diffdate(pgrec['start_date'], date) > 0:
         PgDBI.pgupdt('wuser', new_wuser_record(record, date, False), emcond)
      return record

   # now add one in
   wuid = PgDBI.pgadd("wuser", new_wuser_record(record, date), PgLOG.LOGERR|PgLOG.AUTOID)
   if wuid:
      record['wuid'] = wuid
      PgLOG.pglog("{} Added as wuid({})".format(record['email'], wuid), PgLOG.LGWNEM)
      return record

   return None

def new_wuser_record(iprec, date, nuser = True):

   wurec = {'start_date' : date}
   wurec['org_type'] = iprec['org_type']
   wurec['country'] = iprec['country']
   wurec['region'] = iprec['region']
   if nuser:
      wurec['email'] = iprec['email']
      wurec['stat_flag'] = 'A'

   return wurec
