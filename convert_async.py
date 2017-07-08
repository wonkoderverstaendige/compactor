#!/usr/bin/env python3
import argparse
from pathlib import Path
import asyncio
from asyncio.subprocess import PIPE, STDOUT
import sys
import time
from tqdm import tqdm
import shutil
from collections import namedtuple

COMMAND = 'ffmpeg {overwrite_flag} -hide_banner -i "{in_filepath}" -vf hqdn3d -c:v libx264 -crf {crf} -preset {preset} "{out_filepath}"'
OUTFILE = '{in_filepath.stem}_convert_x264_crf{crf}_{preset}_hqdn3d.avi'
DEFAULT_MAX_PROCS = 3
Result = namedtuple('Result', ['rc', 'in_filepath', 'out_filepath'])


async def convert(in_filepath, output_dir, preset, crf, overwrite=False):
    # t_start = time.time()
    out_filepath = output_dir / Path(OUTFILE.format(**locals()))
    overwrite_flag = '-y' if overwrite else '-n'
    cmd = COMMAND.format(**locals())

    # size_in = in_filepath.stat().st_size

    p = await asyncio.create_subprocess_shell(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout = (await p.communicate())[0].decode('utf-8')
    rc = p.returncode

    # Write stdout into log file
    with open(str(out_filepath) + '.ffmpeg.log', 'w') as ffmpeg_log:
        ffmpeg_log.write(stdout)

    # duration = time.time() - t_start
    #
    try:
        size_out = out_filepath.stat().st_size
    except FileNotFoundError:
        # tqdm.write("{}: Conversion failed!".format(in_filepath))
        size_out = None

    return Result(rc, in_filepath, out_filepath if size_out and not rc else None)


def main(target_path, max_procs=DEFAULT_MAX_PROCS, move_originals=False, *args, **kwargs):
    targets = list(target_path.glob('*.avi'))
    if not len(targets):
        return None

    if sys.platform.startswith('win'):
        loop = asyncio.ProactorEventLoop()  # for subprocess' pipes on Windows
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    output_dir = target_path.joinpath('transcoded')
    if not output_dir.exists():
        Path.mkdir(output_dir)

    pending = []
    results = []
    timestr = time.strftime("%Y%m%d-%H%M%S")
    with tqdm(targets) as pbar:
        while True:
            pending = list(pending)

            # Append tasks
            while len(pending) < max_procs and len(targets):
                pending.append(convert(targets.pop(), output_dir, *args, **kwargs))

            # Check for completed tasks
            done, pending = loop.run_until_complete(asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED))
            results.extend([d.result() for d in done])
            pbar.update(len(done))

            # Stop when all done
            if not len(pending) and not len(targets):
                break

    loop.close()

    # Handle completed conversions
    result_log_path = target_path / 'transcoded_{}.log'.format(timestr)
    with open(result_log_path, 'w+') as success_log:
        for rt in results:
            success_log.write('Inpath: {}, Outpath: {}\n'.format(
                rt.in_filepath,
                rt.out_filepath if rt.out_filepath is not None else '!ERROR ' + str(rt.rc)))

    # Shove converted originals into separate dir
    successes = [result for result in results if not result.rc]
    if move_originals:
        originals_path = target_path / 'originals'
        if not originals_path.exists():
            Path.mkdir(originals_path)

        for result in tqdm(successes, leave=False, desc='Move originals'):
            shutil.move(result.in_filepath, originals_path / result.in_filepath.name)

    # Handle failed conversions
    failures = [result for result in results if result.rc]
    if failures:
        error_log_path = output_dir / 'errors_{}.log'.format(timestr)
        print('Failed to convert {} file(s)! See {} for details.'.format(len(failures), error_log_path))
        with open(error_log_path, 'w+') as error_log:
            for failure in failures:
                error_log.write('Inpath: {}, RC: {}\n'.format(failure.in_filepath, failure.rc))

    sys.exit(len(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser('AVI Conversion')

    parser.add_argument('target', type=str,
                        help='Target directory containing avi files.')
    parser.add_argument('--preset', default='veryfast',
                        help='Encoder preset. Veryfast seems to give great results for some reason.')
    parser.add_argument('-c', '--crf', type=int, default=22,
                        help='CRF quality factor. Decrease to improve quality.')
    parser.add_argument('-P', '--max_procs', type=int, default=DEFAULT_MAX_PROCS,
                        help='Default maximum number of concurrent encoding processes')
    parser.add_argument('-M', '--move_originals', action='store_true', help='Move the originals. Helps with deleting.')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files.')

    cli_args = parser.parse_args()

    main(Path(cli_args.target).resolve(), preset=cli_args.preset, crf=cli_args.crf,
         max_procs=cli_args.max_procs, move_originals=cli_args.move_originals, overwrite=cli_args.overwrite)
