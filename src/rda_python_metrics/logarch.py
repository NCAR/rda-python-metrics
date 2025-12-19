#!/usr/bin/env python3
##################################################################################
#     Title : logarch
#    Author : Zaihua Ji, zji@ucar.edu
#      Date : 11/19/2020
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-utility-programs.git
#             2025-12-17 convert to class LogArch
#   Purpose : archive log files automatically
#    Github : https://github.com/NCAR/rda-python-metrics.git
##################################################################################
import sys
import re
from os import path as op
import glob
from rda_python_common.pg_file import PgFile

class LogArch(PgFile):

   def __init__(self):
      super().__init__()
      # the defined options for archiving different logs
      self.WLOG = 0x21  # archive web log
      self.TLOG = 0x02  # archive tds log
      self.DLOG = 0x04  # archive dssdb logs
      self.SLOG = 0x08  # append dssdb sub batch logs
      self.ALOG = 0x10  # archive AWS web log
      self.OLOG = 0x20  # archive OSDF web log
      self.LOGS = {
         'OPTION' : 0,
         'AWSLOG' : self.PGLOG["TRANSFER"] + "/AWSera5log",
         'WEBLOG' : self.PGLOG["DSSDATA"] + "/work/logs/gridftp",
         'OSDFLOG' : self.PGLOG["DSSDATA"] + "/zji/osdflogs",
         'MGTLOG' : "/data/logs",
         'TDSLOG' : "/data/logs/nginx",
         'RDALOG' : self.PGLOG['LOGPATH'],
         'LOGPATH' : None,
         'CHKLOG' : 1,
         'DECSLOGS' : self.PGLOG['DECSHOME'] + "/DECSLOGS"
      }      
      self.BIDS = {}
      self.smonth = None

   # function to read parameters
   def read_parameters(self):
      pgname = "logarch"
      argv = sys.argv[1:]
      # set different log file
      self.PGLOG['LOGFILE'] = pgname + '.log'
      self.set_suid(self.PGLOG['EUID'])
      option = None
      for arg in argv:
         ms = re.match(r'^-([abdmnpstw])', arg)
         if ms:
            option = ms.group(1)
            if option in 'mp': continue
            if option == "b":
               self.PGLOG['BCKGRND'] = 1
            elif option == "d":
               self.LOGS['OPTION'] |= self.DLOG
            elif option == "w":
               self.LOGS['OPTION'] |= self.WLOG
            elif option == "a":
               self.LOGS['OPTION'] |= self.ALOG
            elif option == "o":
               self.LOGS['OPTION'] |= self.OLOG
            elif option == "s":
               self.LOGS['OPTION'] |= self.SLOG
            elif option == "t":
               self.LOGS['OPTION'] |= self.TLOG
            elif option == "n":
               self.LOGS['CHKLOG'] = 0
            option = None
         elif option == 'm':
            self.smonth = arg
         elif option == 'p':
            self.LOGS['LOGPATH'] = arg
         else:
            self.pglog(arg + ": Invalid Option", self.LGWNEX)
         option = None
      if not self.LOGS['OPTION']: self.show_usage(pgname)
      self.cmdlog("{} {}".format(pgname, ' '.join(argv)))

   # function to start actions
   def start_actions(self):
      if self.LOGS['OPTION']&self.SLOG: self.append_dssdb_sublog()
      if self.LOGS['OPTION']&self.DLOG: self.archive_dssdb_log()
      if self.LOGS['OPTION']&self.WLOG: self.archive_web_log()
      if self.LOGS['OPTION']&self.OLOG: self.archive_osdf_log()
      if self.LOGS['OPTION']&self.ALOG: self.archive_aws_log()
      if self.LOGS['OPTION']&self.TLOG: self.archive_tds_log()
      self.cmdlog(None, 0, self.LOGWRN|self.SNDEML)   

   # get year and month
   def get_year_month(self):
      if not self.smonth: self.smonth = self.adddate(self.curdate('YYYY-MM') + '-01', 0, -1, 0, 'YYYY-MM')
      ms = re.match(r'^(\d+)-(\d+)', self.smonth)
      return [ms.group(1), '{:02}'.format(int(ms.group(2)))]

   # Archive globus web log files to LOGS['DECSLOGS']
   def archive_web_log(self):
      (yr, mn) = self.get_year_month()
      self.change_local_directory(self.LOGS['DECSLOGS'], self.LGEREM)
      logpath = self.LOGS['LOGPATH'] if self.LOGS['LOGPATH'] else self.LOGS['WEBLOG']
      afile = "globusweb{}-{}.log.tar".format(yr, mn)
      dfile = "./WEBLOG/{}.gz".format(afile)
      if op.exists(dfile):
         self.pglog("{}: file exists already under {}, remove it before backup again".format(dfile, self.LOGS['DECSLOGS']), self.LGWNEM)
         return
      if op.exists(afile): self.delete_local_file(afile)
      logfiles = sorted(glob.glob("{}/access_log_gridftp??_{}??{}".format(logpath, mn, yr)))
      topt = '-cvf'
      tcnt = 0
      for logfile in logfiles:
         if not op.exists(logfile):
            self.pglog(logfile + ": file not exists", self.LGWNEM)
            continue
         if  op.getsize(logfile) == 0:
            self.pglog(logfile + ": empty file", self.LGWNEM)
            continue
         lfile = op.basename(logfile)
         tcmd = "tar {} {} -C {} {}".format(topt, afile, logpath, lfile)
         tcnt += self.pgsystem(tcmd, self.LGWNEM, 5)
         topt = '-uvf'   
      if tcnt > 0:
         self.pgsystem("gzip " + afile, self.LGWNEM, 5)
         afile += '.gz'
         self.move_local_file(dfile, afile, self.LGWNEM)
         s = 's' if tcnt > 1 else ''
         self.pglog("{}: {} globus log{} tarred, gzipped and archived at {}".format(afile, tcnt, s, self.current_datetime()), self.LGWNEM)

   # Archive OSDF web log files to self.LOGS['DECSLOGS']
   def archive_osdf_log(self):
      (yr, mn) = self.get_year_month()
      self.change_local_directory(self.LOGS['DECSLOGS'], self.LGEREM)
      logpath = self.LOGS['LOGPATH'] if self.LOGS['LOGPATH'] else self.LOGS['OSDFLOG']
      afile = "osdfweb{}-{}.log.tar".format(yr, mn)
      dfile = "./OSDFLOG/{}.gz".format(afile)
      if op.exists(dfile):
         self.pglog("{}: file exists already under {}, remove it before backup again".format(dfile, self.LOGS['DECSLOGS']), self.LGWNEM)
         return
      if op.exists(afile): self.delete_local_file(afile)
      logfiles = sorted(glob.glob("{}/{}-{}-??.log".format(logpath, yr, mn)))
      topt = '-cvf'
      tcnt = 0
      for logfile in logfiles:
         lfile = op.basename(logfile)
         tcmd = "tar {} {} -C {} {}".format(topt, afile, logpath, lfile)
         tcnt += self.pgsystem(tcmd, self.LGWNEM, 5)
         topt = '-uvf'
      if tcnt > 0:
         self.pgsystem("gzip " + afile, self.LGWNEM, 5)
         afile += '.gz'
         self.move_local_file(dfile, afile, self.LGWNEM)
         s = 's' if tcnt > 1 else ''
         self.pglog("{}: {} globus log{} tarred, gzipped and archived at {}".format(afile, tcnt, s, self.current_datetime()), self.LGWNEM)

   # Archive AWS web log files to self.LOGS['DECSLOGS']
   def archive_aws_log(self):
      (yr, mn) = self.get_year_month()
      self.change_local_directory(self.LOGS['DECSLOGS'], self.LGEREM)
      logpath = self.LOGS['LOGPATH'] if self.LOGS['LOGPATH'] else self.LOGS['AWSLOG']
      afile = "awsweb{}-{}.log.tar".format(yr, mn)
      dfile = "./AWSLOG/{}.gz".format(afile)
      if op.exists(dfile):
         self.pglog("{}: file exists already under {}, remove it before backup again".format(dfile, self.LOGS['DECSLOGS']), self.LGWNEM)
         return
      if op.exists(afile): self.delete_local_file(afile)
      lfile = "{}/{}".format(yr, mn)
      tcmd = "tar -cvf {} -C {} {}".format(afile, logpath, lfile)
      self.pgsystem(tcmd, self.LGWNEM, 5)
      self.pgsystem("gzip " + afile, self.LGWNEM, 5)
      afile += '.gz'
      self.move_local_file(dfile, afile, self.LGWNEM)
      self.pglog("{}: AWS logs tarred, gzipped and archived at {}".format(afile, self.current_datetime()), self.LGWNEM)

   # Archive monthly tds logs under DECSLOGS/TDSLOG/
   def archive_tds_log(self):
      (yr, mn) = self.get_year_month()
      self.change_local_directory(self.LOGS['DECSLOGS'], self.LGEREM)
      logpath = self.LOGS['LOGPATH'] if self.LOGS['LOGPATH'] else self.LOGS['TDSLOG']
      afile = "thredds{}-{}.log.tar".format(yr, mn)
      dfile = "./TDSLOG/{}.gz".format(afile)
      if op.exists(dfile):
         self.pglog("{}: file exists already under {}, remove it before backup again".format(dfile, self.LOGS['DECSLOGS']), self.LGWNEM)
         return
      if op.exists(afile): self.delete_local_file(afile)
      logfiles = sorted(glob.glob("{}/{}-{}-??.access.log".format(logpath, yr, mn)))
      topt = '-cvf'
      tcnt = 0
      for logfile in logfiles:
         if not op.exists(logfile):
            self.pglog(logfile + ": file not exists", self.LGWNEM)
            continue
         if  op.getsize(logfile) == 0:
            self.pglog(logfile + ": empty file", self.LGWNEM)
            continue
         lfile = op.basename(logfile)
         tcmd = "tar {} {} -C {} {}".format(topt, afile, logpath, lfile)
         tcnt += self.pgsystem(tcmd, self.LGWNEM, 5)
         topt = '-uvf'
      if tcnt > 0:
         self.pgsystem("gzip " + afile, self.LGWNEM, 5)
         afile += '.gz'
         self.move_local_file(dfile, afile, self.LGWNEM)
         s = 's' if tcnt > 1 else ''
         self.pglog("{}: {} thredds log{} tarred, gzipped and archived at {}".format(afile, tcnt, s, self.current_datetime()), self.LGWNEM)

   # Archive current dssdb logs  onto hpss under /DSS/RDADB/LOG
   def archive_dssdb_log(self):
      cntall = 0
      logfile = "{}_dblog{}.tar".format(self.PGLOG['HOSTNAME'], self.curdate("YYMMDD"))
      dfile = "{}/RDADB/LOG/{}.gz".format(self.LOGS['DECSLOGS'], logfile)
      if self.LOGS['CHKLOG'] and self.check_decs_archive(dfile):
         return self.pglog(dfile + ": archived already", self.LGWNEM)
      self.change_local_directory(self.LOGS['RDALOG'], self.LWEMEX)
      # collect all the large log/err files
      files = sorted(glob.glob("*.log") + glob.glob("*.err"))
      for file in files:
         info = self.check_local_file(file, 2)
         if(not info or info['data_size'] < 10000): continue   # skip log files small than 10KB
         self.pgsystem("cp -p -f {} backup/{}".format(file, file), self.LWEMEX, 5)
         if info['logname'] != self.PGLOG['GDEXUSER']: self.pgsystem("rm -rf " + file)
         self.pgsystem("cat /dev/null > " + file, 0, 1024)
         if file == 'gdexls.log': self.pgsystem("chmod 666 " + file, 0, 1024)
         if op.exists(logfile):
            self.pgsystem("tar -uvf {} -C backup {}".format(logfile, file), self.LWEMEX, 5)
         else:
            self.pgsystem("tar -cvf {} -C backup {}".format(logfile, file), self.LWEMEX, 5)
         cntall += 1
      if cntall > 0:
         if self.LOGS['CHKLOG']:
            if self.backup_decsdata_file(logfile, logfile, dfile, 1):
               s = 's' if cntall > 1 else ''
               self.pglog("{} dssdb log{} archived at {}".format(cntall, s, self.current_datetime()), self.LGWNEM)
         else:
            self.pgsystem("gzip " + logfile, self.LWEMEX, 5)
            logfile += ".gz"
            self.pgsystem("mv -f {} backup/".format(logfile), self.LWEMEX, 5)

   # append individual batch logs to common stdout/error logs 
   def append_dssdb_sublog(self):
      logpath = self.LOGS['LOGPATH'] if self.LOGS['LOGPATH'] else self.LOGS['RDALOG']
      self.change_local_directory(logpath, self.LGWNEX);   
      if not self.valid_command(self.BCHCMDS['PBS']):
         self.pglog("Must run on PBS Nodes to append sublogs", self.LGEREM)
         return
      self.add_sublog_files('OU', 'log')
      self.add_sublog_files('ER', 'err', 37)

   # add individual sublog files to the common ones
   def add_sublog_files(self, fext, sext, minsize = 0):
      cdate = self.curdate()
      subname = 'rdaqsub'
      pattern = r'^(\d+)\.'
      afiles = self.local_glob("{}/*.{}".format(subname, fext), 3, self.LGWNEX)
      if not afiles:
         self.pglog("{}: NO '{}' file found to collect".format(subname, fext), self.LOGWRN)
         return
      if minsize:
         tmin = self.PGLOG['MINSIZE']
         self.PGLOG['MINSIZE'] = minsize
      acnt = fcnt = 0
      sfiles = {}
      for afile in afiles:
         fcnt += 1
         finfo = afiles[afile]
         sfiles[op.basename(afile)] = [finfo['date_modified'], finfo['time_modified'], finfo['logname']]
      afiles = sorted(sfiles)
      logfile = "PBS_sublog.{}".format(sext)
      for afile in afiles:
         ary = sfiles[afile]
         ms = re.match(pattern, afile)
         if ms:
            bid = int(ms.group(1))
            if bid not in self.BIDS:
               if self.diffdate(cdate, ary[0]) > 6:
                  self.BIDS[bid] = 0
               else:
                  self.BIDS[bid] = self.check_pbs_process(bid, afile)
            if self.BIDS[bid] > 0: continue
         else:
            continue
         sfile = "{}/{}".format(subname, afile)
         if minsize and self.local_file_size(sfile, 1) < 1: continue
         self.pgsystem("echo '{}: {} {} {}' >> {}".format(bid, ary[0], ary[1], ary[2], logfile), self.LGWNEX, 5+1024)
         if self.pgsystem("cat {} >> {}".format(sfile, logfile), self.EMEROL, 5+1024):
            self.delete_local_file(sfile, self.LOGWRN)
            acnt += 1
      if fcnt > 0:
         s = 's' if fcnt > 1 else ''
         self.pglog("{}: {} of {} '{}' file{} appended at {}".format(logfile, acnt, fcnt, fext, s, self.current_datetime()), self.LGWNEM)
      if minsize: self.PGLOG['MINSIZE'] = tmin
   # backup a log file to decsdata area
   def backup_decsdata_file(self, logfile, locfile, dfile, skipcheck = 0):
      ret = 0
      if op.getsize(logfile) == 0:
         self.pglog(logfile + ": Empty log file", self.LGWNEM)
         return 0
      if not skipcheck and self.check_decs_archive(dfile, logfile, 1):
         return 0   # archived already
      if locfile != logfile:
         locfile = "{}/{}".format(self.PGLOG['TMPPATH'], locfile)
         if not self.local_copy_local(locfile, logfile, self.LGWNEM): return 0
      lfile = locfile
      locfile += ".gz"
      if self.check_local_file(locfile, 0, self.LGWNEM): self.delete_local_file(locfile, self.LGWNEM)
      self.pgsystem("gzip " + lfile, self.LWEMEX, 5)
   
      self.pglog("archive {} to {}".format(locfile, dfile), self.LGWNEM)
      if self.local_copy_local(dfile, locfile, self.LGWNEM):
         size = self.check_decs_archive(dfile)
         if size:
            self.pglog("{}: archived as {}({})".format(logfile, dfile, size), self.LGWNEM)
            ret = 1
      if op.exists(locfile) and ret: self.pgsystem("rm -f " + locfile, self.LGWNEM)
      return ret

   # return decs file size if archived already; otherwise 0
   def check_decs_archive(self, afile, logfile = None, checktime = 0):
      ainfo =  self.check_local_file(afile, 1)
      if not ainfo: return 0
      size = ainfo['data_size']
      if logfile:
         linfo = self.check_local_file(logfile, 1, self.LGWNEM)
         if linfo:
            if checktime:
               if linfo['date_modified'] > ainfo['date_modified']: size = 0
            elif size < linfo['data_size']:
               size = 0
         if size > 0: self.pglog("{}: archived on {} as {}({})".format(logfile, ainfo['date_modified'], afile, size), self.LGWNEM)
      return size

# main function to excecute this script
def main():
   object = LogArch()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
