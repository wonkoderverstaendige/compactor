#!/bin/bash

while read line; do
  echo converting "$line";
  echo $outfile;
  base=$(basename "$line" .avi)
  outfile="${base}_reencode_wmv2.avi";
  < /dev/null ffmpeg -i "$line" -q:v 4 -vcodec wmv2 "$outfile";
done

