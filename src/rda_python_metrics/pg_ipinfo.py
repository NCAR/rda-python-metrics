###############################################################################
#     Title : pg_ipinfo
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 08/22/2023
#            2025-03-26 transferred to package rda_python_metrics from
#            https://github.com/NCAR/rda-shared-library.git
#            2025-12-16 convert to class PgIPInfo
#   Purpose : python module to retrieve ip info from ipinfo
#             or geoip2 modules
#    Github : https://github.com/NCAR/rda-python-metrics.git
###############################################################################
import re
import geoip2.database as geodb
import ipinfo
import socket
import dns.resolver
import json
from rda_python_common.pg_dbi import PgDBI
from rda_python_common.pg_util import PgUtil

class PgIPInfo(PgUtil, PgDBI):

   """Retrieve and manage IP geolocation info using ipinfo and geoip2 modules."""

   def __init__(self):
      super().__init__()  # initialize parent class

      self.IPINFO = {
         'TOKEN' : 'b2a67fdd1a9ba3',
         'DBFILE' : self.PGLOG['DSSHOME'] + '/dssdb/GeoLite2-City.mmdb',
         'CDATE' : self.curdate(),
         'IPUPDT' : 0,
         'IPADD'  : 0
      }
      self.GIP = '0.0.0.0'
      self.IPDNS = None
      self.IPDB = None
      self.G2DB = None
      self.IPRECS = {}
      self.DMRECS = {}
      self.COUNTRIES = {}

   def get_dns_resolver(self, forceget = False):
      """Get save a global dns.resolver.Resolver object."""
      if forceget or not self.IPDNS: self.IPDNS = dns.resolver.Resolver()
      return self.IPDNS

   def dns_to_ip(self, dmname, type = 'A'):
      """Resolve a domain name to an IP address (A record)."""
      if dmname in self.DMRECS: return self.DMRECS[dmname]
      ipdns = self.get_dns_resolver()
      dm = None
      try:
         answers = ipdns.resolve(dmname, type)
         dm = [str(rdata) for rdata in answers]
      except dns.resolver.NXDOMAIN:
         self.pglog(f"{dmname}: the domain name does not exist", self.LOGWRN)
      except dns.resolver.Timeout:
         self.pglog(f"{dmname}: the domain name request timed out", self.LOGWRN)
      except dns.exception.DNSException as e:
         self.pglog(f"{dmname}: error domain name request: {e}", self.LOGWRN)
      self.DMRECS[dmname] = dm
      return dm

   def get_country_name_code(self, dm):
      """Get country token name for given two-character domain id."""
      if dm not in self.COUNTRIES:
         pgrec = self.pgget('countries', 'token', "domain_id = '{}'".format(dm))
         self.COUNTRIES[dm] = pgrec['token'] if pgrec else 'Unknown'
      return self.COUNTRIES[dm]

   def get_country_record_code(self, cname, kname = None):
      """Get country code from name."""
      name = cname[kname] if kname else cname
      name = name.replace(' ', '.').upper() if name else 'UNITED.STATES'
      if name == 'CHINA': name = 'P.R.CHINA'
      return name

   def set_ipinfo_database(self):
      """Setup ipinfo database."""
      try:
         self.IPDB = ipinfo.getHandler(self.IPINFO['TOKEN'])
      except Exception as e:
         self.pglog('ipinfo: ' + str(e), self.LGEREX)

   def domain_ipinfo_record(self, dmname):
      """Get a ipinfo record for given domain."""
      ips = self.dns_to_ip(dmname)
      if ips: return self.set_ipinfo(ips[0])
      return None

   def get_ip_hostname(self, ip, iprec, record):
      """Try to get hostname via socket for given ip address."""
      record['hostname'] = ip
      if iprec:
         if 'hostname' in iprec and iprec['hostname']:
            record['hostname'] = iprec['hostname']         
            record['org_type'] = self.get_org_type(None, record['hostname'])
            return
         if 'asn' in iprec and iprec['asn'] and 'domain' in iprec['asn'] and iprec['asn']['domain']:
            record['hostname'] += '.' + iprec['asn']['domain']
            record['org_type'] = self.get_org_type(None, record['hostname'])
            return
      try:
         hostrec = socket.gethostbyaddr(ip)
         record['hostname'] = hostrec[1][0] if hostrec[1] else hostrec[0]
         record['org_type'] = self.get_org_type(None, record['hostname'])
      except Exception as e:
         self.pglog("socket: {} - {}".format(ip, str(e)), self.LOGWRN)

   def get_ipinfo_record(self, ip):
      """Get a ipinfo record for given ip address."""
      if not self.IPDB: self.set_ipinfo_database()
      try:
         iprec = self.IPDB.getDetails(ip).all
      except Exception as e:
         self.pglog("ipinfo: {} - {}".format(ip, str(e)), self.LOGWRN)
         return None
      if 'bogon' in iprec and iprec['bogon']:
         self.pglog(f"ipinfo: {ip} - bogon, use {self.GIP}", self.LOGWRN)
         self.IPRECS[ip] = self.pgget('ipinfo', '*', f"ip = '{self.GIP}'", self.LGEREX)
         return self.IPRECS[ip]
      record = {'ip' : ip, 'stat_flag' : 'A', 'hostname' : ip, 'org_type' : '-'}
      self.get_ip_hostname(ip, iprec, record)
      record['lat'] = float(iprec['latitude']) if iprec['latitude'] else 0
      record['lon'] = float(iprec['longitude']) if iprec['longitude'] else 0
      if 'org' in iprec: record['org_name'] = iprec['org']
      record['country'] = self.get_country_record_code(iprec, 'country_name')
      record['region'] = self.convert_chars(iprec['region']) if 'region' in iprec else None
      if 'city' in iprec: record['city'] = self.convert_chars(iprec['city'])
      if 'postal' in iprec: record['postal'] =  iprec['postal']
      record['timezone'] = iprec['timezone']
      record['ipinfo'] = json.dumps(iprec)
      return record

   def set_geoip2_database(self):
      """Setup geoip2 database."""
      try:
         self.G2DB = geodb.Reader(self.IPINFO['DBFILE'])
      except Exception as e:
         self.pglog("geoip2: " + str(e), self.LGEREX)

   def get_geoip2_record(self, ip):
      """Get a geoip2 record for given ip address."""
      if not self.G2DB: self.set_geoip2_database()
      try:
         city = self.G2DB.city(ip)
      except Exception as e:
         self.pglog("geoip2: {} - {}".format(ip, str(e)), self.LOGWRN)
         return None
      record = {'ip' : ip, 'stat_flag' : 'M', 'org_type' : '-'}
      self.get_ip_hostname(ip, None, record)
      record['lat'] = float(city.location.latitude) if city.location.latitude else 0
      record['lon'] = float(city.location.longitude) if city.location.longitude else 0
      record['country'] = self.get_country_record_code(city.country.name)
      record['city'] = self.convert_chars(city.city.name)
      record['region'] = self.convert_chars(city.subdivisions.most_specific.name) if city.subdivisions.most_specific.name else None
      record['postal'] =  city.postal.code
      record['timezone'] = city.location.time_zone
      record['ipinfo'] = json.dumps(self.object_to_dict(city))
      return record

   def object_to_dict(self, obj):
      """Change an object to dict recursively."""
      if hasattr(obj, "__dict__"):
         result = {}
         for key, value in obj.__dict__.items():
            result[key] = self.object_to_dict(value)
         return result
      elif isinstance(obj, list):
         return [self.object_to_dict(item) for item in obj]
      else:
         return obj

   def update_wuser_email(self, nhost, ohost):
      """Update wuser.email for hostname changed."""
      pgrec = self.pgget('wuser', 'wuid', "email = 'unknown@{}'".format(ohost))
      if pgrec: self.pgexec("UPDATE wuser SET email = 'unknown@{}' WHERE wuid = {}".format(nhost, pgrec['wuid']))

   def update_ipinfo_record(self, record, pgrec = None):
      """Update a ipinfo record; add a new one if not exists yet."""
      tname = 'ipinfo'
      cnd = "ip = '{}'".format(record['ip'])
      if not pgrec: pgrec = self.pgget(tname, '*', cnd)
      if pgrec:
         nrec = self.get_update_record(record, pgrec)
         if 'hostname' in nrec: self.update_wuser_email(nrec['hostname'], pgrec['hostname'])
         ret = self.pgupdt(tname, nrec, cnd) if nrec else 0
         self.IPINFO['IPUPDT'] += ret
      else:
         record['adddate'] = self.IPINFO['CDATE']
         ret = self.pgadd(tname, record)
         self.IPINFO['IPADD'] += ret
      return ret

   def set_ipinfo(self, ip, ipopt = True):
      """If ipopt is True; otherwise, use module geoip2."""
      if ip in self.IPRECS: return self.IPRECS[ip]
      pgrec = self.pgget('ipinfo', '*', "ip = '{}'".format(ip))
      if not pgrec or ipopt and pgrec['stat_flag'] == 'M':
         record = self.get_ipinfo_record(ip) if ipopt else None
         if not record: record = self.get_geoip2_record(ip)
         if record:
            self.update_ipinfo_record(record, pgrec)
            pgrec = record
      self.IPRECS[ip] = pgrec
      return pgrec

   def get_update_record(self, nrec, orec):
      """Compare and return a new record holding fields with different values only."""
      record = {}   
      for fld in nrec:
         if nrec[fld] != orec[fld]:
            record[fld] = nrec[fld]
      return record

   def get_missing_ipinfo(self, ip, email = None, gethost = False):
      """Fill the missing info for given ip."""
      if not ip:
         if email and '@' in email: ip = self.dns_to_ip(email.split('@')[1])
         if not ip: return None
         ip = ip[0]
      ipinfo = self.set_ipinfo(ip)
      if ipinfo:
         record = {'org_type' : ipinfo['org_type'],
                   'country' : ipinfo['country'],
                   'region' : ipinfo['region'],
                   'ip' : ipinfo['ip']}
         if not email or re.search(r'-$', email):
            record['email'] =  'unknown@' + ipinfo['hostname']
         else:
            record['email'] = email
         if gethost: record['hostname'] = ipinfo['hostname']

         return record
      else:
         return None

   def get_wuser_record(self, ip, date, email = None):
      """Return wuser record upon success, None otherwise."""
      record = self.get_missing_ipinfo(ip, email)
      if not record: return None
      emcond = "email = '{}'".format(record['email'])
      flds = 'wuid, start_date'   
      pgrec = self.pgget("wuser", flds, emcond, self.LOGERR)
      if pgrec:
         record['wuid'] = pgrec['wuid']
         if self.diffdate(pgrec['start_date'], date) > 0:
            self.pgupdt('wuser', self.new_wuser_record(record, date, False), emcond)
         return record
      # now add one in
      wuid = self.pgadd("wuser", self.new_wuser_record(record, date), self.LOGERR|self.AUTOID)
      if wuid:
         record['wuid'] = wuid
         self.pglog("{} Added as wuid({})".format(record['email'], wuid), self.LGWNEM)
         return record
      return None

   def new_wuser_record(self, iprec, date, nuser = True):
      """Create a new wuser record."""
      wurec = {'start_date' : date}
      wurec['org_type'] = iprec['org_type']
      wurec['country'] = iprec['country']
      wurec['region'] = iprec['region']
      if nuser:
         wurec['email'] = iprec['email']
         wurec['stat_flag'] = 'A'
      return wurec
