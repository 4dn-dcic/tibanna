#!/usr/bin/python
import sys

n = int(sys.argv[1]) # original number
M = int(sys.argv[2]) # max size for split range

nsplit = n//M
if nsplit*M<n:
  nsplit+=1
ninterval = n//nsplit
ncum=1
end=0
while end < n:
  start=ncum
  ncum += ninterval
  end=ncum-1
  if end>n:
    end=n
  print( "{0}-{1}".format(start,end) )

