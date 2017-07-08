from pathlib import Path
import subprocess as sp
import argparse
import sys
import time

COMMAND = 'ffmpeg -y -hide_banner -i "{inpath}" -vf hqdn3d -c:v libx264 -crf {crf} -preset {preset} -psnr -ssim 1 "{outpath}"'
OUTPATH = '{inpath.stem}_convert_x264_crf{crf}_{preset}_hqdn3d.avi'


def encode(inpath, crf, preset, out_dir):
    t_start = time.time()
    outpath = out_dir / Path(OUTPATH.format(**locals()))
    command = COMMAND.format(**locals())
    
    size_in = inpath.stat().st_size

    print('\nTranscoding {}, {:.2f} MB'.format(inpath.name, size_in/1e6))
    with open(str(outpath) + '.ffmpeg.log', 'w') as ffmpeg_log:
        p = sp.Popen(command, shell=True, stdout=sp.PIPE, stderr=sp.STDOUT)
        ffmpeg_log.write(command + '\n')
        for line in p.stdout.readlines():
            ffmpeg_log.write(line.decode('utf-8'))
        rv = p.wait()
        duration = time.time() - t_start
        
        if not rv:
            size_out = outpath.stat().st_size
            print("{}, {:.2f} MB, compression: {:.2f}x".format(fmt_time(duration), size_out/1e6, size_in/size_out))
            ffmpeg_log.write('Duration: {}'.format(duration))
            return preset, duration, size_out, crf
        else:
            ffmpeg_log.write('ERROR')


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


def main(target, crf, preset):
    target_path = Path(target)
    if target_path.is_dir():
        paths = target_path.glob('*.avi')
    else:
        paths = [target_path]
    path_list = [p.resolve() for p in paths if not 'x264' in p.name]
    
    out_dir = Path(path_list[0].parent / 'transcoded')
    if not out_dir.exists():
        Path.mkdir(out_dir)
        print("Made output directory", out_dir)
    
    for p in path_list:
        encode(p, crf, preset, out_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser('Video Conversion')

    parser.add_argument('target', type=str)
    parser.add_argument('--preset', default='veryfast')
    parser.add_argument('-c', '--crf', type=int, default=22)

    cli_args = parser.parse_args()
    main(cli_args.target, preset=cli_args.preset, crf=cli_args.crf)
