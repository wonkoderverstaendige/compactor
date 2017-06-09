#!/usr/bin/env python

from pathlib import Path
import subprocess as sp
import argparse
import logging
import sys

LEN_FC2_FILES = 35
PRESETS = ('ultrafast','superfast', 'veryfast', 'faster', 'fast', 'medium', 'slow', 'slower', 'veryslow', 'placebo')

def main(target, codec='libx264', crf='22', preset='fast', count_only=True):

    target_path = Path(target).resolve()

    vids = [v for v in target_path.glob('fc2_save_*.avi') if len(v.name) == LEN_FC2_FILES]
    print('Found {} matching files in {}'.format(len(vids), target_path))

    # taking file names apart
    stems = [v.stem for v in vids]
    times = [v[:-5] for v in stems]

    # count number of fragments for unique timestamps
    fragments = {v: times.count(v) for v in times}
    print('Found {} unique timestamps in filenames'.format(len(fragments)))

    if count_only:
        sys.exit(0)
    container = 'avi' if codec == 'libx264' else 'mp4'
    # Create batches of timestamps for concatenation
    for k, v in fragments.items():
        print('timestamp {} has {} parts.'.format(k, v))
        with open('next_vids.txt', 'w+') as t:
            for n in range(v):
                p = target_path.joinpath('{}-{:04d}.avi'.format(k, n))
                assert(p.exists())
                t.write("file '{}'\n".format(p))
                print("file '{}'\n".format(p))

   
        outfile = k + '_converted_x264_crf{crf}_{preset}.{container}'.format(crf=crf, preset=preset, container=container)
        command = 'ffmpeg -f concat -safe 0 -i {listfile} -vf scale=-1:720 -c:v libx264 -preset {preset} -crf {crf} convert/{outfile}'.format(
                listfile='next_vids.txt',
                codec=codec,
                preset=preset,
                crf=crf,
                outfile=outfile)
        # Try command
        print(command)
        res = sp.check_call(command, shell=True)
        assert(not res)
        #if not res:
        #   # all went well
        #   # append current files to potential deleties:



if __name__ == "__main__":
    parser = argparse.ArgumentParser('Video Conversion')

    parser.add_argument('target', type=str)
    parser.add_argument('--codec', choices=('libx264', 'libx265'), default='libx264')
    parser.add_argument('--preset', choices=PRESETS, default='veryslow')
    parser.add_argument('-c', '--crf', type=int, default=22)

    cli_args = parser.parse_args()
    main(cli_args.target, preset=cli_args.preset, crf=cli_args.crf, codec=cli_args.codec)

    

