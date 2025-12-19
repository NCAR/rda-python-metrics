#!/usr/bin/env python3
#*******************************************************************
#     Title : pgperson.py
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2025-03-27
#             2025-12-19 convert to class PgPerson
#   Purpose : utility program to retrieve user info from People DB
#    Github : https://github.com/NCAR/rda-python-metrics.git
#*******************************************************************
import httplib2
import json
import sys

class PgPerson:

   def __init__(self):
      super().__init__()
      self.PERSON = [
         "upid",          # Unique person id
         "username",      # UCAR login  user name
         "email",         # Email address
         "uid",           # Scientist id or Unix id
         "firstName",     # First name
         "lastName",      # Last name
         "forwardEmail"   # Forward Email address
      ]
      self.urlfmt = "https://people.api.ucar.edu/persons?{}={}&searchScope=all&includeActive=true&includeInactive=true&searchType=advancedSearch"
      self.option = self.optval = None

   # function to read parameters
   def read_parameters(self):
      pgname = "pgperson"
      argv = sys.argv[1:]
      argc = len(sys.argv)
      optstr = '|'.join(self.PERSON)
      if argc != 3:
         print("Usage: {} -({}) OptopnValue".format(pgname, optstr))
         sys.exit(0)
      for arg in argv:
         if self.option:
            self.optval = arg
         elif arg[0] == '-':
            self.option = arg[1:]
            if self.option not in self.PERSON:
               print("{}: unknown option, must be -({})".format(arg, optstr), sys.stderr)
         else:
            print("{}: Value passed in without leading option -({})".format(arg, optstr), sys.stderr)

   # function to start actions
   def start_actions(self):
      headers = {'Content-type': 'application/json'}
      http=httplib2.Http()
      url = self.urlfmt.format(self.option, self.optval)
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

# main function to excecute this script
def main():
   object = PgPerson()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
