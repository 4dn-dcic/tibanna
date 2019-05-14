#!/usr/bin/perl
$max=0;
while(<>){
  s/^\s+//g;
  ($m)=(split/\s+/)[5];
  if($m=~/m$/) { $m = $`; $m *= 1024; }
  if($m=~/g$/) { $g = $`; $m *= 1024 * 1024; }
  if($m > $max) { $max = $m; }
}
$max /= 1024*1024;
print("$max\n");

