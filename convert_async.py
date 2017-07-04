#!/usr/bin/env python3
import argparse
from pathlib import Path
import asyncio
from asyncio.subprocess import PIPE, STDOUT
import sys
import time

COMMAND = 'ffmpeg -y -hide_banner -i "{in_filepath}" -vf hqdn3d -c:v libx264 -crf 22 -preset veryfast "{out_filepath}"'
OUTFILE = '{in_filepath.stem}_convert_x264_crf22_veryfast_hqdn3d.avi'
DEFAULT_MAX_PROCS = 3


def fmt_time(s, minimal=True):
    """
    Args:
        s: time in seconds (float for fractional)
        minimal: Flag, if true, only return strings for times > 0, leave rest outs
    Returns: String formatted 99h 59min 59.9s, where elements < 1 are left out optionally.
    """
    ms = s - int(s)
    s = int(s)
    if s < 60 and minimal:
        return "{s:02.3f}s".format(s=s + ms)

    m, s = divmod(s, 60)
    if m < 60 and minimal:
        return "{m:02d}min {s:02.3f}s".format(m=m, s=s + ms)

    h, m = divmod(m, 60)
    return "{h:02d}h {m:02d}min {s:02.3f}s".format(h=h, m=m, s=s + ms)


async def convert(in_filepath, output_dir):
    t_start = time.time()
    out_filepath = output_dir / Path(OUTFILE.format(**locals()))
    cmd = COMMAND.format(**locals())

    size_in = in_filepath.stat().st_size

    print('Starting {}, {:.2f} MB'.format(in_filepath, size_in / 1e6))

    p = await asyncio.create_subprocess_shell(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout = (await p.communicate())[0].decode('utf-8')

    # Write stdout into log file
    with open(str(out_filepath) + '.ffmpeg.log', 'w') as ffmpeg_log:
        ffmpeg_log.write(stdout)

    size_out = out_filepath.stat().st_size
    duration = time.time() - t_start
    print("{}: {}, {:.2f} MB, compression: {:.2f}x".format(out_filepath, fmt_time(duration), size_out / 1e6,
                                                           size_in / size_out))
    return out_filepath


def main(target_path, preset, crf, max_procs=DEFAULT_MAX_PROCS):
    if sys.platform.startswith('win'):
        loop = asyncio.ProactorEventLoop()  # for subprocess' pipes on Windows
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    output_dir = target_path.joinpath('transcode')
    if not output_dir.exists():
        Path.mkdir(output_dir)
        print("Made output directory", output_dir)

    targets = list(target_path.glob('*.avi'))

    pending = []
    while True:
        pending = list(pending)

        # Append tasks
        while len(pending) < max_procs and len(targets):
            pending.append(convert(targets.pop(), output_dir))

        # Check for completed tasks
        done, pending = loop.run_until_complete(asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED))
        # for d in done:
        #     print('Finished', d.result())

        # Stop when all done
        if not len(pending) and not len(targets):
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser('Video Conversion')

    parser.add_argument('target', type=str,
                        help='Target directory containing avi files.')
    parser.add_argument('--preset', default='veryfast',
                        help='Encoder preset. Veryfast seems to give great results for some reason.')
    parser.add_argument('-c', '--crf', type=int, default=22,
                        help='CRF quality factor. Decrease to improve quality.')
    parser.add_argument('-P', '--max_procs', type=int, default=DEFAULT_MAX_PROCS,
                        help='Default maximum number of concurrent encoding processes')

    cli_args = parser.parse_args()

    main(Path(cli_args.target).resolve(), preset=cli_args.preset, crf=cli_args.crf,
         max_procs=cli_args.max_procs)
