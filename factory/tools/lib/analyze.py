from __future__ import print_function
########################
# Library for analyze_entries,
#   analyze_queues and analyze_frontends.
########################

import os, sys, getopt, re
import datetime
import urllib

# Convert particularly large numbers
#    into kilo/mega; keeps 3 sig figs
# Example: km(123456) returns "123 K"
#      and km(1234567) returns "1.23 M"
def km(z):

   if z<0: neg = "-"
   else: neg = "" 
   z = abs(z)

   x = int(z)
   w = z*1.0e-3
   v = z*1.0e-6
   t = z*1.0e-9
   if x>=1000:
      if x>=1000 and x<1000000:
         return "%s%.1fK" % (neg, w)
      if x>=1000000 and x<1000000000:
         return "%s%.1fM" % (neg, v)
      if x>=1000000000:
         return "%s%.1fG" % (neg, t)
   else: return "%s%.1f" % (neg, z)

# prints a dictionary with \n and \t 
#    between elements for ease of debugging.

def debug_print_dict(data):
   for period, p in list(data.items()):
      print(period)
      for frontend, f in list(p.items()):
         print("\t", frontend)
         for entry, e in list(f.items()):
            print("\t\t", entry)
            for element, value in list(e.items()):
               print("\t\t\t", element, ":", value)
   return

#Prints a line formatted the following way:
# printline(1234, 7200 (2 days), total) returns: 
# "1.2K (.34 hours - .17 slots - %XX of total)" 
# Set div = 1 to omit percentage of total
 
def printline(x, div, period):
   if div==1:
      sp = ""
   else:
      try:
         sp = " - %2d%%" % ((float(x)/float(div))*100)
      except:
         sp = " - NA%"
   return ("%6s (%6s hours - %5s slots%s)"
      % (km(x),
         km(float(x)/3600.0),
         km(float(x)/float(period)),
         sp))

