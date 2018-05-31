#!/usr/bin/python
import sys
import csv

def split_num(n, M):
    # n : original number
    # M : max size for split range

    nsplit = n//M
    if nsplit*M<n:
        nsplit+=1
    ninterval = n//nsplit
    ncum=1
    end=0
    res=[]
    while end < n:
        start=ncum
        ncum += ninterval
        end=ncum-1
        if end>n:
            end=n
        res.append("{0}-{1}".format(start, end))
    return res
    
def split_num_given_args ():
    n = int(sys.argv[1]) # original number
    M = int(sys.argv[2]) # max size for split range
    print split_num (n, M)


def split_chrom (chromsize_file, M):
    with open(chromsize_file, 'r') as f:
        reader = csv.reader(f, delimiter='\t') 
        for row in reader:
            for interval in split_num (int(row[1]), int(M) ):
                print ( "{chr}:{interval}".format(chr=row[0], interval=interval) )

if __name__ == "__main__":
        import argparse

        parser = argparse.ArgumentParser(description="Arguments")
        parser.add_argument("-c", "--chrom", help="Chrom.size file, tab-delimited")
        parser.add_argument("-M", "--max_split_size", help="Maximum split size")
        args = parser.parse_args()

        split_chrom(args.chrom, args.max_split_size)


