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
from ipinfo.exceptions import RequestQuotaExceededError
import dns.resolver
import dns.reversename
import json
import ipaddress
from concurrent.futures import ThreadPoolExecutor
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
         'IPADD'  : 0,
         'QUOTA'  : 1,   # unset when the ipinfo monthly request quota is used up
         'DNSTMO' : 2,   # seconds to wait on a single name server
         'DNSLTM' : 5,   # seconds to spend on one name resolution in total
         'DNSTHD' : 16,  # number of threads used to presolve a list of ip addresses
         'IPFAIL' : 0,   # ipinfo calls that failed in a row
         'MAXFAIL' : 5,  # give ipinfo up for the run after this many in a row
         'ALLFAIL' : 0,  # ipinfo calls that failed at all in this run
         'MAXALL' : 50   # give ipinfo up for the run after this many altogether
      }
      self.GIP = '0.0.0.0'
      self.DNSTMOUT = object()   # marks a reverse lookup that ran out of time
      self.BOGONIP = object()    # marks an address ipinfo reports as a bogon
      self.IPDNS = None
      self.IPDB = None
      self.G2DB = None
      self.IPRECS = {}
      self.DMRECS = {}
      self.IPDMS = {}
      self.IPNRM = {}
      self.IPSKP = {}
      self.COUNTRIES = {}

   def normalize_ip(self, ip):
      """Return the canonical form of an ip address; empty string if it is not valid.

      One IPv6 address can be written several ways, upper or lower case and with the
      zero groups spelled out or collapsed, and the IPv4-embedded form is longer than
      the 39 characters ipinfo.ip holds. Canonicalizing on the way in keeps one row
      and one set of usage records per address whichever way a log spells it.
      """
      if ip in self.IPNRM: return self.IPNRM[ip]
      try:
         nip = ipaddress.ip_address(ip).compressed
      except ValueError:
         self.pglog("{}: invalid ip address".format(ip), self.LOGWRN)
         nip = ''
      self.IPNRM[ip] = nip
      return nip

   def get_dns_resolver(self, forceget = False):
      """Get save a global dns.resolver.Resolver object."""
      if forceget or not self.IPDNS:
         self.IPDNS = dns.resolver.Resolver()
         self.IPDNS.timeout = self.IPINFO['DNSTMO']
         self.IPDNS.lifetime = self.IPINFO['DNSLTM']
         self.IPDNS.cache = dns.resolver.Cache()
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
      dm = dm.lower() if dm else ''
      if not dm: return 'Unknown'
      if dm not in self.COUNTRIES:
         pgrec = self.pgget('countries', 'token', "LOWER(domain_id) = '{}'".format(dm))
         self.COUNTRIES[dm] = pgrec['token'] if pgrec else 'Unknown'
      return self.COUNTRIES[dm]

   def get_country_record_code(self, cname, kname = None, code = None):
      """Get country code from name, falling back to a two-character country code.

      An address whose country cannot be named at all is UNKNOWN, which is what
      email_to_country() already gives for an address it cannot place. It used to
      be UNITED.STATES: a guess rather than a default, which filed every unnamed
      address under one country and left it indistinguishable from the addresses
      genuinely there. A geoip2 city record and an ipinfo Lite answer both carry
      the two character code even where the name is missing, so try that first.
      """
      name = cname.get(kname) if kname else cname
      if not name and code: name = self.get_country_name_code(code)
      name = name.replace(' ', '.').upper() if name else 'UNKNOWN'
      if name == 'CHINA': name = 'P.R.CHINA'
      return name

   def set_ipinfo_database(self):
      """Setup ipinfo database.

      The account is an ipinfo Lite one, which answers on its own endpoint and is
      not metered. getHandler() asks ipinfo.io instead, where the same token has
      no allowance left and every call comes back 429, which tripped the quota
      breaker on the first address of every run and left geoip2 to do all of it.
      """
      try:
         self.IPDB = ipinfo.getHandlerLite(self.IPINFO['TOKEN'])
      except Exception as e:
         self.pglog('ipinfo: ' + str(e), self.LGEREX)

   def domain_ipinfo_record(self, dmname):
      """Get a ipinfo record for given domain."""
      ips = self.dns_to_ip(dmname)
      if ips: return self.set_ipinfo(ips[0])
      return None

   def reverse_resolve_ip(self, ip):
      """Reverse resolve one ip address without logging; called from worker threads too.

      Returns tuple (ip, hostname, errmsg); hostname is empty if the ip has no PTR
      record, and errmsg is self.DNSTMOUT for a lookup that ran out of time.
      """
      try:
         answers = self.IPDNS.resolve(dns.reversename.from_address(ip), 'PTR')
         # an ip may have several PTR records, answered in varying order; always pick
         # the same one so the host name on file does not flip between runs
         if answers: return (ip, min([str(a).rstrip('.') for a in answers]), None)
      except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
         pass   # no PTR record on file for the ip, too common to be worth logging
      except dns.exception.Timeout:
         # address space whose authoritative servers are slow, far away or gone runs
         # out of time routinely; counted in the presolve summary rather than logged
         # one line per address, which buried the DNS errors worth reading
         return (ip, '', self.DNSTMOUT)
      except dns.exception.DNSException as e:
         return (ip, '', "{}: error reverse domain name request: {}".format(ip, e))
      return (ip, '', None)

   def ip_to_dns(self, ip):
      """Reverse resolve an ip address to a host name; empty string if none."""
      if ip in self.IPDMS: return self.IPDMS[ip]
      self.get_dns_resolver()
      (ip, dm, errmsg) = self.reverse_resolve_ip(ip)
      if errmsg and errmsg is not self.DNSTMOUT: self.pglog(errmsg, self.LOGWRN)
      self.IPDMS[ip] = dm
      return dm

   def prescan_ips(self, fd, pattern, group = 1):
      """Scan an open log file for ip addresses, presolve them, and rewind the file.

      A fill program reads its log line by line and looks each new ip up as it goes,
      which serializes one slow reverse DNS lookup per address. Picking the addresses
      out in a first cheap pass lets preset_ip_hostnames() resolve them several at a
      time, so the main loop finds the host names already cached.
      """
      ips = {}
      for line in fd:
         ms = re.match(pattern, line)
         if ms: ips[ms.group(group)] = 1
      fd.seek(0)
      return self.preset_ip_hostnames(list(ips))

   def get_recorded_ips(self, ips):
      """Return a dict of the given ip addresses that have an ipinfo record on file."""
      recorded = {}
      for i in range(0, len(ips), 1000):
         vals = ', '.join(["'{}'".format(ip) for ip in ips[i:i+1000]])
         pgrecs = self.pgmget('ipinfo', 'ip', "ip IN ({})".format(vals), self.LOGWRN)
         if pgrecs:
            for ip in pgrecs['ip']: recorded[ip] = 1
      return recorded

   def preset_ip_hostnames(self, ips):
      """Reverse resolve a list of ip addresses in parallel and cache the host names.

      Resolving one ip at a time is the slowest part of gathering usage from a large
      log file. Doing the new ones up front, several at a time, leaves the host names
      in self.IPDMS for get_ip_hostname() to pick up without waiting again.
      """
      ips = [ip for ip in {self.normalize_ip(ip) for ip in ips}
             if ip and ip not in self.IPDMS and ip not in self.IPSKP]
      if not ips: return 0
      # ips on file are either reused as is or refreshed by ipinfo, which carries its
      # own host name, so only the ones not on file are worth resolving ahead of time.
      # remember which ones those were, or every later log file queries them again
      recorded = self.get_recorded_ips(ips)
      self.IPSKP.update(recorded)
      newips = [ip for ip in ips if ip not in recorded]
      if not newips: return 0
      self.get_dns_resolver()   # create the shared resolver before starting the threads
      cnt = tmocnt = 0
      with ThreadPoolExecutor(max_workers = self.IPINFO['DNSTHD']) as executor:
         for (ip, dm, errmsg) in executor.map(self.reverse_resolve_ip, newips):
            if errmsg is self.DNSTMOUT:
               tmocnt += 1
            elif errmsg:
               self.pglog(errmsg, self.LOGWRN)
            self.IPDMS[ip] = dm
            if dm: cnt += 1
      msg = "{}/{} host names presolved for {} IP addresses".format(cnt, len(newips), len(ips))
      # a large share timing out means the lifetime is too short for the address
      # space in this log, which DNSLTM and DNSTHD can be raised to cover
      if tmocnt: msg += ", {} timed out after {}s".format(tmocnt, self.IPINFO['DNSLTM'])
      self.pglog(msg, self.LOGWRN)
      return cnt

   def ipinfo_network_domain(self, iprec):
      """The domain owning the ip's network, as ipinfo names it; '' if it names none.

      Lite answers with a flat 'as_domain'; the standard API nests the same thing
      under 'asn', which Lite gives as the plain AS number instead.
      """
      if not iprec: return ''
      if iprec.get('as_domain'): return iprec['as_domain']
      asn = iprec.get('asn')
      if isinstance(asn, dict) and asn.get('domain'): return asn['domain']
      return ''

   def get_ip_hostname(self, ip, iprec, record):
      """Try to get hostname via reverse DNS for given ip address.

      A name ipinfo resolved itself is taken as is, but the network domain is only
      a fallback: it names the operator rather than the host, so 8.8.8.8 becomes
      8.8.8.8.google.com where a reverse lookup would have said dns.google. Trying
      it after DNS keeps the better name wherever there is one, and still fills in
      something usable for the addresses whose reverse lookup times out.
      """
      record['hostname'] = ip
      if iprec and iprec.get('hostname'):
         record['hostname'] = iprec['hostname']
         record['org_type'] = self.get_org_type(None, record['hostname'])
         return
      dm = self.ip_to_dns(ip)
      if not dm:
         dmname = self.ipinfo_network_domain(iprec)
         if dmname: dm = "{}.{}".format(ip, dmname)
      if dm:
         record['hostname'] = dm
         record['org_type'] = self.get_org_type(None, dm)

   def unset_ipinfo_quota(self, reason = 'monthly request quota used up'):
      """Stop calling ipinfo for the rest of the run, naming why."""
      if self.IPINFO['QUOTA']:
         self.IPINFO['QUOTA'] = 0
         self.pglog("ipinfo: {}, use geoip2 for the rest of the run".format(reason), self.LOGWRN)

   def get_ipinfo_answer(self, ip):
      """Ask ipinfo about an ip address; returns its answer, or None.

      Only the call and what to do when it fails live here. The answer is laid
      over a geoip2 record by get_geoip2_record(), an ipinfo Lite answer carrying
      the network and the country but none of the geography.
      """
      if not self.IPINFO['QUOTA']: return None
      if not self.IPDB: self.set_ipinfo_database()
      try:
         iprec = self.IPDB.getDetails(ip).all
      except RequestQuotaExceededError:
         self.unset_ipinfo_quota()
         return None
      except Exception as e:
         estr = str(e)
         if re.search(r'(\b429\b|quota)', estr, re.I):
            self.unset_ipinfo_quota()
         else:
            self.pglog("ipinfo: {} - {}".format(ip, estr), self.LOGWRN)
            # a host that cannot reach ipinfo.io fails the same way for every
            # address, and each try costs the full request timeout, so stop
            # asking rather than spend the run timing out one ip at a time
            self.IPINFO['IPFAIL'] += 1
            self.IPINFO['ALLFAIL'] += 1
            if self.IPINFO['IPFAIL'] >= self.IPINFO['MAXFAIL']:
               self.unset_ipinfo_quota("{} calls in a row failed".format(self.IPINFO['IPFAIL']))
            elif self.IPINFO['ALLFAIL'] >= self.IPINFO['MAXALL']:
               # ipinfo answering some calls and timing out on others keeps resetting
               # the in-a-row count above, so cap what the whole run may waste too
               self.unset_ipinfo_quota("{} calls failed".format(self.IPINFO['ALLFAIL']))
         return None
      self.IPINFO['IPFAIL'] = 0   # reachable again, so an odd failure does not add up
      if iprec and iprec.get('bogon'):
         self.pglog(f"ipinfo: {ip} - bogon, use {self.GIP}", self.LOGWRN)
         return self.BOGONIP
      return iprec

   def set_geoip2_database(self):
      """Setup geoip2 database."""
      try:
         self.G2DB = geodb.Reader(self.IPINFO['DBFILE'])
      except Exception as e:
         self.pglog("geoip2: " + str(e), self.LGEREX)

   def get_geoip2_record(self, ip, iprec = None):
      """Get a geoip2 record for given ip address, with any ipinfo answer laid over it.

      Neither source is complete on its own. The local geoip2 city database holds
      the geography and knows nothing about the network; an ipinfo Lite answer
      holds the network and the country and none of the geography. So geoip2 is
      the record and ipinfo overwrites the fields it is the better authority for,
      which leaves the record as complete as the two together can make it.

      An answer with neither city nor network beyond what geoip2 already had still
      counts: stat_flag 'A' marks the ip as asked about, and 'M' leaves it to be
      asked about again on a later run.
      """
      if not self.G2DB: self.set_geoip2_database()
      try:
         city = self.G2DB.city(ip)
      except Exception as e:
         self.pglog("geoip2: {} - {}".format(ip, str(e)), self.LOGWRN)
         return None
      record = {'ip' : ip, 'stat_flag' : 'A' if iprec else 'M', 'org_type' : '-'}
      self.get_ip_hostname(ip, iprec, record)
      record['lat'] = float(city.location.latitude) if city.location.latitude else 0
      record['lon'] = float(city.location.longitude) if city.location.longitude else 0
      record['country'] = self.get_country_record_code(city.country.name, None, city.country.iso_code)
      record['city'] = self.convert_chars(city.city.name)
      record['region'] = self.convert_chars(city.subdivisions.most_specific.name) if city.subdivisions.most_specific.name else None
      record['postal'] =  city.postal.code
      record['timezone'] = city.location.time_zone
      record['ipinfo'] = json.dumps(self.object_to_dict(city))
      if iprec: self.merge_ipinfo_answer(record, iprec)
      return record

   def merge_ipinfo_answer(self, record, iprec):
      """Lay an ipinfo answer over a geoip2 record, field by field.

      Only the fields ipinfo is the better authority for are taken: the country it
      names for the address, and the network operating it. Geography a Lite answer
      does not carry is left as geoip2 gave it, so this never empties a field that
      was filled. An answer shaped differently again must not end the run, so a
      merge that cannot be made leaves the geoip2 record as it stands.
      """
      try:
         if iprec.get('country_name') or iprec.get('country') or iprec.get('country_code'):
            record['country'] = self.get_country_record_code(
               iprec, 'country_name' if iprec.get('country_name') else 'country',
               iprec.get('country_code'))
         orgname = iprec.get('as_name') or iprec.get('org')
         if orgname: record['org_name'] = orgname
         for fld in ('region', 'city', 'postal', 'timezone'):
            if iprec.get(fld): record[fld] = self.convert_chars(iprec[fld])
         if iprec.get('latitude'): record['lat'] = float(iprec['latitude'])
         if iprec.get('longitude'): record['lon'] = float(iprec['longitude'])
         record['ipinfo'] = json.dumps(iprec)
      except (KeyError, TypeError, ValueError) as e:
         self.pglog("ipinfo: {} - unusable answer ({}: {}), use geoip2".format(
                    record['ip'], type(e).__name__, e), self.LOGWRN)

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
      ip = self.normalize_ip(ip)
      if not ip: return None
      if ip in self.IPRECS: return self.IPRECS[ip]
      if ipopt and not self.IPINFO['QUOTA']: ipopt = False   # quota used up, geoip2 only
      pgrec = self.pgget('ipinfo', '*', "ip = '{}'".format(ip))
      if not pgrec or ipopt and pgrec['stat_flag'] == 'M':
         iprec = self.get_ipinfo_answer(ip) if ipopt else None
         if iprec is self.BOGONIP:
            # a bogon address is nobody's; they all share the one record on file
            self.IPRECS[ip] = self.pgget('ipinfo', '*', f"ip = '{self.GIP}'", self.LGEREX)
            return self.IPRECS[ip]
         record = self.get_geoip2_record(ip, iprec)
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
