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
      response, content = http.request(self.url + self.uname, 'GET', headers=headers)
      status = response.status
      if status == 200:
         person=json.loads(content)
         for key, value in person.items():
            print("{}<=>{}".format(key, value))
      elif status == 399:
         print(content)
      elif status == 500:
         print('Server error')

# main function to excecute this script
def main():
   object = PgUserName()
   object.read_parameters()
   object.start_actions()
   object.pgexit(0)

# call main() to start program
if __name__ == "__main__": main()
