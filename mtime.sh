#!/bin/bash

TMPFILE=`mktemp /tmp/mtime.XXXXXX` || exit 1

for x in {1..100}
do
  gtime -f "real %e user %U sys %S" -a -o $TMPFILE "$@"
  #tail -1 $TMPFILE
done

awk '{ et += $2; ut += $4; st += $6; count++ } END {  printf "%d iterations\n", count ; printf "average: real %.3f user %.3f sys %.3f\n", et/count, ut/count, st/count }' $TMPFILE

rm $TMPFILE

