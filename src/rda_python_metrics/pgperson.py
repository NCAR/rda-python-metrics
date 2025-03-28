#!/usr/bin/env python3
#*******************************************************************
#     Title : pgperson.py
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2025-03-27
#   Purpose : utility program to retrieve user info from People DB
#
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
#*******************************************************************

import httplib2
import json
import sys
from rda_python_common import PgLOG

PERSON = [
   "upid",          # Unique person id
   "username",      # UCAR login  user name
   "email",         # Email address
   "uid",           # Scientist id or Unix id
   "firstName",     # First name
   "lastName",      # Last name
   "forwardEmail"   # Forward Email address
]

urlfmt="https://people.api.ucar.edu/persons?{}={}&searchScope=all&includeActive=true&includeInactive=true&searchType=advancedSearch"

#
# main function to excecute this script
#
def main():

   pgname = "pgperson"
   argv = sys.argv[1:]
   optstr = '|'.join(PERSON)
   if sys.argc != 3:
      print("Usage: {} -({}) OptopnValue".format(pgname, optstr))
      sys.exit(0)

   option = optval = None
   for arg in argv:
      if option:
         optval = arg
      elif arg[0] == '-':
         option = arg[1:]
         if option not in PERSON:
            PgLOG.pglog("{}: unknown option, must be -({})".format(arg, optstr), PgLOG.LGEREX)
      else:
         PgLOG.pglog("{}: Value passed in without leading option -({})".format(arg, optstr), PgLOG.LGEREX)

   headers = {'Content-type': 'application/json'}
   http=httplib2.Http()
   url = urlfmt.format(option, optval)
   response, content = http.request(url, 'GET', headers=headers)
   status = response.status
   if status == 200:
      persons=json.loads(content)
      for person in persons:
         for key, value in person.items():
            print("{}<=>{}".format(key, value))
   elif status == 399:
      print(content)
   elif status == 500:
      print('Server error')

   sys.exit(0)

#
# call main() to start program
#
if __name__ == "__main__": main()
