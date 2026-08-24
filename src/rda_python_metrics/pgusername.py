#!/usr/bin/env python3
#*******************************************************************
#     Title : pgusername.py
#    Author : Zaihua Ji,  zji@ucar.edu
#      Date : 2025-03-27
#             2025-12-19 convert to class PgUserName
#   Purpose : utility program to retrieve user info from People DB
#             for a given UCAR user login name
#    Github : https://github.com/NCAR/rda-python-metrics.git
#*******************************************************************
import httplib2
import json
import sys

class PgUserName:

   def __init__(self):
      super().__init__()
      self.url="https://people.api.ucar.edu/usernames/"
      self.uname = None

   # function to read parameters
   def read_parameters(self):
      pgname = "pgusername"
      argc = len(sys.argv)
      if argc != 2:
         print("Usage: {} UserName".format(pgname))
         sys.exit(0)
      self.uname = sys.argv[1]

   # function to start actions
   def start_actions(self):
      headers = {'Content-type': 'application/json'}
      http=httplib2.Http()
      url = self.url + self.uname
      response, content = http.request(url, 'GET', headers=headers)
      status = response.status
      if status != 200:
         print("pgusername: HTTP {} from {}\n{}".format(status, url, content.decode(errors='replace')), file=sys.stderr)
         sys.exit(1)
      person=json.loads(content)
      for key, value in person.items():
         print("{}<=>{}".format(key, value))

# main function to execute this script
def main():
   object = PgUserName()
   object.read_parameters()
   object.start_actions()
   sys.exit(0)

# call main() to start program
if __name__ == "__main__": main()
