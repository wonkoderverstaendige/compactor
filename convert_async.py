#!/usr/bin/env python3
import argparse
from pathlib import Path
import asyncio
from asyncio.subprocess import PIPE, STDOUT
import sys
import time
from tqdm import tqdm

COMMAND = 'ffmpeg -y -hide_banner -i "{in_filepath}" -vf hqdn3d -c:v libx264 -crf 22 -preset veryfast "{out_filepath}"'
OUTFILE = '{in_filepath.stem}_convert_x264_crf22_veryfast_hqdn3d.avi'
DEFAULT_MAX_PROCS = 3


async def convert(in_filepath, output_dir):
    t_start = time.time()
    out_filepath = output_dir / Path(OUTFILE.format(**locals()))
    cmd = COMMAND.format(**locals())

    size_in = in_filepath.stat().st_size

    # tqdm.write('Starting {}, {:.2f} MB'.format(in_filepath, size_in / 1e6))

    p = await asyncio.create_subprocess_shell(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout = (await p.communicate())[0].decode('utf-8')

    # Write stdout into log file
    with open(str(out_filepath) + '.ffmpeg.log', 'w') as ffmpeg_log:
        ffmpeg_log.write(stdout)

    duration = time.time() - t_start

    try:
        size_out = out_filepath.stat().st_size
        # tqdm.write("{}: {}, {:.2f} MB, compression: {:.2f}x".format(out_filepath, fmt_time(duration),
        #                                                        size_out / 1e6,
        #                                                        size_in / size_out))
    except FileNotFoundError:
        # tqdm.write("{}: Conversion failed!".format(in_filepath))
        size_out = None

    return size_out, in_filepath, out_filepath


def main(target_path, preset, crf, max_procs=DEFAULT_MAX_PROCS):
    targets = list(target_path.glob('*.avi'))
    if not len(targets):
        return None

    if sys.platform.startswith('win'):
        loop = asyncio.ProactorEventLoop()  # for subprocess' pipes on Windows
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    output_dir = target_path.joinpath('transcode')
    if not output_dir.exists():
        Path.mkdir(output_dir)
        print("Made output directory", output_dir)

    pending = []
    results = []
    timestr = time.strftime("%Y%m%d-%H%M%S")
    with tqdm(targets) as pbar:
        while True:
            pending = list(pending)

            # Append tasks
            while len(pending) < max_procs and len(targets):
                pending.append(convert(targets.pop(), output_dir))

            # Check for completed tasks
            done, pending = loop.run_until_complete(asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED))
            results.extend([d.result() for d in  done])
            pbar.update(len(done))

            # Stop when all done
            if not len(pending) and not len(targets):
                break

    loop.close()

    # Handle failed conversions
    failures = [result for result in results if not result[0]]
    if failures:
        error_log_path = output_dir / 'errors_{}.log'.format(timestr)
        print('Failed to convert {} file(s)! See {} for details.'.format(len(failures), error_log_path))
        with open(error_log_path, 'w+') as error_log:
            for failure in failures:
                error_log.write(str(failure[1]))
    sys.exit(len(failures))



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
