#!/bin/bash

while read line; do
  echo converting "$line";
  echo $outfile;
  base=$(basename "$line" .avi)
  outfile="${base}_reencode.avi";
  < /dev/null ffmpeg -i "$line" -c:v libx264 -preset veryslow -crf 23 "$outfile";
done

