#!/usr/bin/env python3
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio
from asyncio.subprocess import PIPE, STDOUT
import sys
import time
from tqdm import tqdm
from collections import namedtuple
import shutil

COMMAND = 'ffmpeg {overwrite_flag} -f  concat -safe 0 -i "{tmp_file.name}" ' \
          '-vf hqdn3d -c:v libx264 -crf {crf} -preset {preset} -pix_fmt yuv420p "{out_filepath}"'

LONG_OUTFILE = '{batch_key.stem}_x264_crf{crf}_{preset}_hqdn3d.avi'
SHORT_OUTFILE = '{batch_key.stem}.mp4'

DEFAULT_GLOB = '*.avi'
DEFAULT_FC2_GLOB = 'fc2_save_????-??-??-??????-####.avi'

DEFAULT_MAX_PROCS = 3

RESULT_FILE_EXISTS = -1
RESULT_CODE_DICT = {-1: 'File exists, not overwriting.'}
Result = namedtuple('Result', ['rc', 'in_files', 'out_filepath'])


async def async_convert(batch_item, output_dir, output_name, tmp_dir, preset, crf, scale=None, overwrite=False):
    overwrite_flag = '-y' if overwrite else '-n'
    batch_key, in_files = batch_item
    out_filepath = output_dir / Path(output_name.format(**locals()))

    if not overwrite and out_filepath.exists():
        return Result(RESULT_FILE_EXISTS, in_files, out_filepath)

    with open(tmp_dir / (batch_key.stem + '.tmp'), 'w+') as tmp_file:
        for f in in_files:
            tmp_file.write("file '{}'\n".format(f))

    cmd = COMMAND.format(**locals())
    p = await asyncio.create_subprocess_shell(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout = (await p.communicate())[0].decode('utf-8')
    rc = p.returncode

    # Write stdout into log file
    with open(str(out_filepath) + '.ffmpeg.log', 'w') as ffmpeg_log:
        ffmpeg_log.write(stdout)

    try:
        size_out = out_filepath.stat().st_size
    except FileNotFoundError:
        size_out = None

    return Result(rc=rc, in_files=in_files, out_filepath=out_filepath)


def main():
    # FIXME Glob exclusion (e.g. 'x264')
    # FIXME Python version enforcement

    parser = argparse.ArgumentParser('AVI Conversion')

    parser.add_argument('target', type=str, default='.',
                        help='Target directory containing avi files.')
    parser.add_argument('--preset', default='veryfast',
                        help='Encoder preset. Veryfast seems to give great results for some reason.')
    parser.add_argument('-c', '--crf', type=int, default=18,
                        help='CRF quality factor. Decrease to improve quality.')
    parser.add_argument('-P', '--max_procs', type=int, default=DEFAULT_MAX_PROCS,
                        help='Maximum number of concurrent encoding processes (default {})'.format(DEFAULT_MAX_PROCS))
    parser.add_argument('-O', '--move_originals', action='store_true', help='Move the originals. Helps with deleting.')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files.')
    parser.add_argument('-g', '--glob', default=DEFAULT_GLOB, help='Glob pattern for target selection.')

    parser.add_argument('-M', '--masked', action='store_true', help='File glob has mask')
    parser.add_argument('-m', '--mask', help='File glob pattern and mask. Overrides glob.', default=DEFAULT_FC2_GLOB)
    parser.add_argument('-Q', '--quality_naming', help='Append quality parameters to output filename.',
                        action='store_true')

    cli_args = parser.parse_args()

    glob = cli_args.mask.replace('#', '?') if cli_args.masked else cli_args.glob
    target_path = Path(cli_args.target).resolve()
    files = sorted(target_path.glob(glob))
    if not files:
        print('No matching files found.')
        return

    if cli_args.masked:
        print(f'Running in masked file name mode with mask {cli_args.mask}')
        stems = set([''.join([l if cli_args.mask[n] != '#' else '#' for n, l in enumerate(f.name)]) for f in files])
        batches = {Path(m).resolve(): [Path(sm).resolve() for sm in sorted(target_path.glob(m.replace('#', '?')))] for m in stems}

    else:
        batches = {bs: [bs] for bs in files}

    print(f'Found {len(files)} matching files in {len(batches)} batches.')

    if sys.platform.startswith('win'):
        loop = asyncio.ProactorEventLoop()  # for subprocess' pipes on Windows
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.get_event_loop()

    output_dir = target_path.joinpath('transcoded')
    if not output_dir.exists():
        Path.mkdir(output_dir)

    output_name = LONG_OUTFILE if cli_args.quality_naming else SHORT_OUTFILE

    time_str = time.strftime("%Y%m%d-%H%M%S")
    result_log_path = target_path / 'compactor_{}.log'.format(time_str)

    results = []
    pending = set()
    with TemporaryDirectory() as tmp_dir, tqdm(files, unit='avi') as pbar:
        tmp_dir_path = Path(tmp_dir).resolve()

        while True:
            # Add tasks
            while len(pending) < cli_args.max_procs and len(batches):
                pending.add(async_convert(
                    batches.popitem(), output_dir=output_dir, output_name=output_name, tmp_dir=tmp_dir_path,
                    crf=cli_args.crf, preset=cli_args.preset, overwrite=cli_args.overwrite)
                )

            # Check for completed tasks
            done, pending = loop.run_until_complete(asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED))
            results_done = [d.result() for d in done]
            results.extend(results_done)
            pbar.update(sum([len(r.in_files) for r in results_done]))

            # Stop when all done
            if not len(pending) and not len(batches):
                break

    originals_path = target_path / 'originals'
    if cli_args.move_originals and not originals_path.exists():
        Path.mkdir(originals_path)

    # Handle results, both successes and failures
    with open(result_log_path, 'w+') as result_log:
        for result in results:
            # Write result to crappy log file
            result_log.write('Inpath: {}, Outpath: {}\n'.format(
                result.in_files,
                result.out_filepath if not result.rc else '!ERROR ' + str(result.rc)))

            # Shove successfully converted originals into separate dir
            if result.rc == 0 and cli_args.move_originals:
                    for in_file in result.in_files:
                        shutil.move(in_file, originals_path / in_file.name)

    # Handle failed conversions
    failures = [result for result in results if result.rc != 0]
    if failures:
        error_log_path = output_dir / 'errors_{}.log'.format(time_str)
        print('Failed to convert {} file(s)! See {} for details.'.format(len(failures), error_log_path))
        with open(error_log_path, 'w+') as error_log:
            for failure in failures:
                error = RESULT_CODE_DICT[failure.rc] if failure.rc < 0 else f'FFMPEG return code {failure.rc}'
                error_log.write('Inpath: {}, RC: {}\n'.format(failure.in_files, error))

    loop.close()
    sys.exit(len(failures))


if __name__ == "__main__":
    main()
