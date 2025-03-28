#!/usr/bin/env python3
#*******************************************************************
#     Title : pgusername.py
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2025-03-27
#   Purpose : utility program to retrieve user info from People DB
#             for a given UCAR user login name
#
#    Github : https://github.com/NCAR/rda-python-metrics.git
#
#*******************************************************************

import httplib2
import json
import sys
from rda_python_common import PgLOG

url="https://people.api.ucar.edu/usernames/"

#
# main function to excecute this script
#
def main():

   pgname = "pgusername"
   if sys.argc != 2:
      print("Usage: {} UserName".format(pgname))
      sys.exit(0)

   uname = sys.argv[1]

   headers = {'Content-type': 'application/json'}
   http=httplib2.Http()
   response, content = http.request(url + uname, 'GET', headers=headers)
   status = response.status
   if status == 200:
      person=json.loads(content)
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
