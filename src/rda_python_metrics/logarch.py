#!/usr/bin/env python3
#
##################################################################################
#
#     Title : logarch
#    Author : Zaihua Ji, zji@ucar.edu
#      Date : 11/19/2020
#             2025-03-26 transferred to package rda_python_metrics from
#             https://github.com/NCAR/rda-utility-programs.git
#   Purpose : archive log files automatically
#
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
##################################################################################

import sys
import re
from os import path as op
import glob
from rda_python_common import PgLOG
from rda_python_common import PgUtil
from rda_python_common import PgFile
from rda_python_common import PgSIG

# the defined options for archiving different logs
WLOG = 0x21  # archive web log
TLOG = 0x02  # archive tds log
DLOG = 0x04  # archive dssdb logs
SLOG = 0x08  # append dssdb sub batch logs
ALOG = 0x10  # archive AWS web log
OLOG = 0x20  # archive OSDF web log

LOGS = {
   'OPTION' : 0,
   'AWSLOG' : PgLOG.PGLOG["TRANSFER"] + "/AWSera5log",
   'WEBLOG' : PgLOG.PGLOG["DSSDATA"] + "/work/logs/gridftp",
   'OSDFLOG' : PgLOG.PGLOG["DSSDATA"] + "/zji/osdflogs",
   'MGTLOG' : "/data/logs",
   'TDSLOG' : "/data/logs/nginx",
   'RDALOG' : PgLOG.PGLOG['LOGPATH'],
   'LOGPATH' : None,
   'CHKLOG' : 1,
   'DECSLOGS' : PgLOG.PGLOG['DECSHOME'] + "/DECSLOGS"
}

BIDS = {}

#
# main function to excecute this script
#
def main():

   pgname = "logarch"
   argv = sys.argv[1:]
   smonth = None

   # set different log file
   PgLOG.PGLOG['LOGFILE'] = pgname + '.log'
   PgLOG.set_suid(PgLOG.PGLOG['EUID'])
   
   option = None
   for arg in argv:
      ms = re.match(r'^-([abdmnpstw])', arg)
      if ms:
         option = ms.group(1)
         if option in 'mp': continue
         if option == "b":
            PgLOG.PGLOG['BCKGRND'] = 1
         elif option == "d":
            LOGS['OPTION'] |= DLOG
         elif option == "w":
            LOGS['OPTION'] |= WLOG
         elif option == "a":
            LOGS['OPTION'] |= ALOG
         elif option == "o":
            LOGS['OPTION'] |= OLOG
         elif option == "s":
            LOGS['OPTION'] |= SLOG
         elif option == "t":
            LOGS['OPTION'] |= TLOG
         elif option == "n":
            LOGS['CHKLOG'] = 0
         option = None
      elif option == 'm':
         smonth = arg
      elif option == 'p':
         LOGS['LOGPATH'] = arg
      else:
         PgLOG.pglog(arg + ": Invalid Option", PgLOG.LGWNEX)
      option = None

   if not LOGS['OPTION']: PgLOG.show_usage(pgname)
   PgLOG.cmdlog("{} {}".format(pgname, ' '.join(argv)))

   if LOGS['OPTION']&SLOG: append_dssdb_sublog()
   if LOGS['OPTION']&DLOG: archive_dssdb_log()
   if LOGS['OPTION']&WLOG: archive_web_log(smonth)
   if LOGS['OPTION']&OLOG: archive_osdf_log(smonth)
   if LOGS['OPTION']&ALOG: archive_aws_log(smonth)
   if LOGS['OPTION']&TLOG: archive_tds_log(smonth)

   PgLOG.cmdlog(None, 0, PgLOG.LOGWRN|PgLOG.SNDEML)   
   PgLOG.pgexit(0)

def get_year_month(smonth):

   if not smonth: smonth = PgUtil.adddate(PgUtil.curdate('YYYY-MM') + '-01', 0, -1, 0, 'YYYY-MM')
   ms = re.match(r'^(\d+)-(\d+)', smonth)
   return [ms.group(1), '{:02}'.format(int(ms.group(2)))]

#
# Archive globus web log files to LOGS['DECSLOGS']
#
def archive_web_log(smonth):

   (yr, mn) = get_year_month(smonth)
   PgFile.change_local_directory(LOGS['DECSLOGS'], PgLOG.LGEREM)
   logpath = LOGS['LOGPATH'] if LOGS['LOGPATH'] else LOGS['WEBLOG']
   afile = "globusweb{}-{}.log.tar".format(yr, mn)
   dfile = "./WEBLOG/{}.gz".format(afile)
   if op.exists(dfile):
      PgLOG.pglog("{}: file exists already under {}, remove it before backup again".format(dfile, LOGS['DECSLOGS']), PgLOG.LGWNEM)
      return

   if op.exists(afile): PgFile.delete_local_file(afile)

   logfiles = sorted(glob.glob("{}/access_log_gridftp??_{}??{}".format(logpath, mn, yr)))
   topt = '-cvf'
   tcnt = 0
   for logfile in logfiles:
      if not op.exists(logfile):
         PgLOG.pglog(logfile + ": file not exists", PgLOG.LGWNEM)
         continue
      if  op.getsize(logfile) == 0:
         PgLOG.pglog(logfile + ": empty file", PgLOG.LGWNEM)
         continue
      lfile = op.basename(logfile)
      tcmd = "tar {} {} -C {} {}".format(topt, afile, logpath, lfile)
      tcnt += PgLOG.pgsystem(tcmd, PgLOG.LGWNEM, 5)
      topt = '-uvf'

   
   if tcnt > 0:
      PgLOG.pgsystem("gzip " + afile, PgLOG.LGWNEM, 5)
      afile += '.gz'
      PgFile.move_local_file(dfile, afile, PgLOG.LGWNEM)
      s = 's' if tcnt > 1 else ''
      PgLOG.pglog("{}: {} globus log{} tarred, gzipped and archived at {}".format(afile, tcnt, s, PgLOG.current_datetime()), PgLOG.LGWNEM)

#
# Archive OSDF web log files to LOGS['DECSLOGS']
#
def archive_osdf_log(smonth):

   (yr, mn) = get_year_month(smonth)
   PgFile.change_local_directory(LOGS['DECSLOGS'], PgLOG.LGEREM)
   logpath = LOGS['LOGPATH'] if LOGS['LOGPATH'] else LOGS['OSDFLOG']
   afile = "osdfweb{}-{}.log.tar".format(yr, mn)
   dfile = "./OSDFLOG/{}.gz".format(afile)
   if op.exists(dfile):
      PgLOG.pglog("{}: file exists already under {}, remove it before backup again".format(dfile, LOGS['DECSLOGS']), PgLOG.LGWNEM)
      return

   if op.exists(afile): PgFile.delete_local_file(afile)

   logfiles = sorted(glob.glob("{}/{}-{}-??.log".format(logpath, yr, mn)))
   topt = '-cvf'
   tcnt = 0
   for logfile in logfiles:
      lfile = op.basename(logfile)
      tcmd = "tar {} {} -C {} {}".format(topt, afile, logpath, lfile)
      tcnt += PgLOG.pgsystem(tcmd, PgLOG.LGWNEM, 5)
      topt = '-uvf'
   
   if tcnt > 0:
      PgLOG.pgsystem("gzip " + afile, PgLOG.LGWNEM, 5)
      afile += '.gz'
      PgFile.move_local_file(dfile, afile, PgLOG.LGWNEM)
      s = 's' if tcnt > 1 else ''
      PgLOG.pglog("{}: {} globus log{} tarred, gzipped and archived at {}".format(afile, tcnt, s, PgLOG.current_datetime()), PgLOG.LGWNEM)

#
# Archive AWS web log files to LOGS['DECSLOGS']
#
def archive_aws_log(smonth):

   (yr, mn) = get_year_month(smonth)
   PgFile.change_local_directory(LOGS['DECSLOGS'], PgLOG.LGEREM)
   logpath = LOGS['LOGPATH'] if LOGS['LOGPATH'] else LOGS['AWSLOG']
   afile = "awsweb{}-{}.log.tar".format(yr, mn)
   dfile = "./AWSLOG/{}.gz".format(afile)
   if op.exists(dfile):
      PgLOG.pglog("{}: file exists already under {}, remove it before backup again".format(dfile, LOGS['DECSLOGS']), PgLOG.LGWNEM)
      return

   if op.exists(afile): PgFile.delete_local_file(afile)

   lfile = "{}/{}".format(yr, mn)
   tcmd = "tar -cvf {} -C {} {}".format(afile, logpath, lfile)
   PgLOG.pgsystem(tcmd, PgLOG.LGWNEM, 5)

   PgLOG.pgsystem("gzip " + afile, PgLOG.LGWNEM, 5)
   afile += '.gz'
   PgFile.move_local_file(dfile, afile, PgLOG.LGWNEM)
   PgLOG.pglog("{}: AWS logs tarred, gzipped and archived at {}".format(afile, PgLOG.current_datetime()), PgLOG.LGWNEM)

#
# Archive monthly tds logs under DECSLOGS/TDSLOG/
#
def archive_tds_log(smonth):

   (yr, mn) = get_year_month(smonth)
   PgFile.change_local_directory(LOGS['DECSLOGS'], PgLOG.LGEREM)
   logpath = LOGS['LOGPATH'] if LOGS['LOGPATH'] else LOGS['TDSLOG']
   afile = "thredds{}-{}.log.tar".format(yr, mn)
   dfile = "./TDSLOG/{}.gz".format(afile)
   if op.exists(dfile):
      PgLOG.pglog("{}: file exists already under {}, remove it before backup again".format(dfile, LOGS['DECSLOGS']), PgLOG.LGWNEM)
      return

   if op.exists(afile): PgFile.delete_local_file(afile)

   logfiles = sorted(glob.glob("{}/{}-{}-??.access.log".format(logpath, yr, mn)))
   topt = '-cvf'
   tcnt = 0
   for logfile in logfiles:
      if not op.exists(logfile):
         PgLOG.pglog(logfile + ": file not exists", PgLOG.LGWNEM)
         continue
      if  op.getsize(logfile) == 0:
         PgLOG.pglog(logfile + ": empty file", PgLOG.LGWNEM)
         continue
      lfile = op.basename(logfile)
      tcmd = "tar {} {} -C {} {}".format(topt, afile, logpath, lfile)
      tcnt += PgLOG.pgsystem(tcmd, PgLOG.LGWNEM, 5)
      topt = '-uvf'

   if tcnt > 0:
      PgLOG.pgsystem("gzip " + afile, PgLOG.LGWNEM, 5)
      afile += '.gz'
      PgFile.move_local_file(dfile, afile, PgLOG.LGWNEM)
      s = 's' if tcnt > 1 else ''
      PgLOG.pglog("{}: {} thredds log{} tarred, gzipped and archived at {}".format(afile, tcnt, s, PgLOG.current_datetime()), PgLOG.LGWNEM)

#
# Archive current dssdb logs  onto hpss under /DSS/RDADB/LOG
#
def archive_dssdb_log():

   cntall = 0
   logfile = "{}_dblog{}.tar".format(PgLOG.PGLOG['HOSTNAME'], PgUtil.curdate("YYMMDD"))
   dfile = "{}/RDADB/LOG/{}.gz".format(LOGS['DECSLOGS'], logfile)
   if LOGS['CHKLOG'] and check_decs_archive(dfile):
      return PgLOG.pglog(dfile + ": archived already", PgLOG.LGWNEM)

   PgFile.change_local_directory(LOGS['RDALOG'], PgLOG.LWEMEX)

   # collect all the large log/err files
   files = sorted(glob.glob("*.log") + glob.glob("*.err"))
   for file in files:
      info = PgFile.check_local_file(file, 2)
      if(not info or info['data_size'] < 10000): continue   # skip log files small than 10KB

      PgLOG.pgsystem("cp -p -f {} backup/{}".format(file, file), PgLOG.LWEMEX, 5)
      if info['logname'] != PgLOG.PGLOG['RDAUSER']: PgLOG.pgsystem("rm -rf " + file)
      PgLOG.pgsystem("cat /dev/null > " + file, 0, 1024)
      if op.exists(logfile):
         PgLOG.pgsystem("tar -uvf {} -C backup {}".format(logfile, file), PgLOG.LWEMEX, 5)
      else:
         PgLOG.pgsystem("tar -cvf {} -C backup {}".format(logfile, file), PgLOG.LWEMEX, 5)
      cntall += 1

   if cntall > 0:
      if LOGS['CHKLOG']:
         if backup_decsdata_file(logfile, logfile, dfile, 1):
            s = 's' if cntall > 1 else ''
            PgLOG.pglog("{} dssdb log{} archived at {}".format(cntall, s, PgLOG.current_datetime()), PgLOG.LGWNEM)
      else:
         PgLOG.pgsystem("gzip " + logfile, PgLOG.LWEMEX, 5)
         logfile += ".gz"
         PgLOG.pgsystem("mv -f {} backup/".format(logfile), PgLOG.LWEMEX, 5)

#
# append individual batch logs to common stdout/error logs 
#
def append_dssdb_sublog():

   logpath = LOGS['LOGPATH'] if LOGS['LOGPATH'] else LOGS['RDALOG']
   PgFile.change_local_directory(logpath, PgLOG.LGWNEX);   

   if not PgLOG.valid_command(PgLOG.BCHCMDS['PBS']):
      PgLOG.pglog("Must run on PBS Nodes to append sublogs", PgLOG.LGEREM)
      return

   add_sublog_files('OU', 'log')
   add_sublog_files('ER', 'err', 37)

#
# add individual sublog files to the common ones
#
def add_sublog_files(fext, sext, minsize = 0):

   subname = 'rdaqsub'
   pattern = r'^(\d+)\.'
   afiles = PgFile.local_glob("{}/*.{}".format(subname, fext), 3, PgLOG.LGWNEX)
   if not afiles:
      PgLOG.pglog("{}: NO '{}' file found to collect".format(subname, fext), PgLOG.LOGWRN)
      return
   if minsize:
      tmin = PgLOG.PGLOG['MINSIZE']
      PgLOG.PGLOG['MINSIZE'] = minsize
   acnt = fcnt = 0
   sfiles = {}
   for afile in afiles:
      fcnt += 1
      finfo = afiles[afile]
      sfiles[op.basename(afile)] = "{} {} {}".format(finfo['date_modified'], finfo['time_modified'], finfo['logname'])

   afiles = sorted(sfiles)
   logfile = "PBS_sublog.{}".format(sext)
   for afile in afiles:
      ms = re.match(pattern, afile)
      if ms:
         bid = int(ms.group(1))
         if bid not in BIDS: BIDS[bid] = PgSIG.check_pbs_process(bid, afile)
         if BIDS[bid] > 0: continue
      else:
         continue

      sfile = "{}/{}".format(subname, afile)
      if minsize and PgFile.local_file_size(sfile, 1) < 1: continue
      PgLOG.pgsystem("echo '{}: {}' >> {}".format(bid, sfiles[afile], logfile), PgLOG.LGWNEX, 5+1024)
      PgLOG.pgsystem("cat {} >> {}".format(sfile, logfile), PgLOG.LGWNEX, 5+1024)
      PgFile.delete_local_file(sfile, PgLOG.LOGWRN)
      acnt += 1
   if fcnt > 0:
      s = 's' if fcnt > 1 else ''
      PgLOG.pglog("{}: {} of {} '{}' file{} appended at {}".format(logfile, acnt, fcnt, fext, s, PgLOG.current_datetime()), PgLOG.LOGWRN)

   if minsize: PgLOG.PGLOG['MINSIZE'] = tmin

#
# backup a log file to decsdata area
#
def backup_decsdata_file(logfile, locfile, dfile, skipcheck = 0):
   
   ret = 0
   if op.getsize(logfile) == 0:
      PgLOG.pglog(logfile + ": Empty log file", PgLOG.LGWNEM)
      return 0
   if not skipcheck and check_decs_archive(dfile, logfile, 1):
      return 0   # archived already

   if locfile != logfile:
      locfile = "{}/{}".format(PgLOG.PGLOG['TMPPATH'], locfile)
      if not PgFile.local_copy_local(locfile, logfile, PgLOG.LGWNEM): return 0
   lfile = locfile
   locfile += ".gz"
   if PgFile.check_local_file(locfile, 0, PgLOG.LGWNEM): PgFile.delete_local_file(locfile, PgLOG.LGWNEM)
   PgLOG.pgsystem("gzip " + lfile, PgLOG.LWEMEX, 5)

   PgLOG.pglog("archive {} to {}".format(locfile, dfile), PgLOG.LGWNEM)
   if PgFile.local_copy_local(dfile, locfile, PgLOG.LGWNEM):
      size = check_decs_archive(dfile)
      if size:
         PgLOG.pglog("{}: archived as {}({})".format(logfile, dfile, size), PgLOG.LGWNEM)
         ret = 1
   
   if op.exists(locfile) and ret: PgLOG.pgsystem("rm -f " + locfile, PgLOG.LGWNEM)

   return ret

#
# return decs file size if archived already; otherwise 0
#
def check_decs_archive(afile, logfile = None, checktime = 0):
   
   ainfo =  PgFile.check_local_file(afile, 1)
   if not ainfo: return 0
   size = ainfo['data_size']
   if logfile:
      linfo = PgFile.check_local_file(logfile, 1, PgLOG.LGWNEM)
      if linfo:
         if checktime:
            if linfo['date_modified'] > ainfo['date_modified']: size = 0
         elif size < linfo['data_size']:
            size = 0

      if size > 0: PgLOG.pglog("{}: archived on {} as {}({})".format(logfile, ainfo['date_modified'], afile, size), PgLOG.LGWNEM)

   return size

#
# call main() to start program
#
if __name__ == "__main__": main()
