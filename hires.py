#!/usr/bin/env python3

if __name__ == '__main__':
	import argparse
	from math import log
	from os.path import split, join
	from os import cpu_count
	from doom.util import chain_args, get_chains, mkzip, hires
	from doom.graphic import png_to_waifu2x

	parser = argparse.ArgumentParser(
		description='Generate a hires package using an AI image scalar. '
			'Builds appropriate filters for IWAD chains. You may safely use the resulting package with all IWAD/PWAD chains specified.'
	)
	chain_args(parser)
	parser.add_argument(
		'-scale',
		nargs='?',
		help='Scale graphics to X times the original size. Only accepts the original size or doubles. (1x, 2x, 4x, 8x)',
		default=2,
		type=int
	)
	parser.add_argument(
		'-gpu',
		nargs='?',
		help='Pass gpu option to waifu2x-chainer, otherwise just use cpu. Requires NVIDIA graphics card and Cupy.',
		default=-1,
		type=int
	)
	parser.add_argument(
		'-cpu',
		help='How many cpu workers to use, otherwise dont use multiprocessing. "0" will match the CPU cores on the system. Prone to crashing when used with gpu.',
		default=1,
		type=int
	)
	parser.add_argument(
		'-path',
		help='Directory to extract files to. Also determines name and location of PK3.'
	)
	parser.add_argument(
		'-nopk3',
		action='store_true',
		help='Dont create the PK3 normally provided for convenience'
	)
	
	args = parser.parse_args()
	chains = get_chains(args)

	doubles = log(args.scale, 2)
	if not doubles.is_integer():
		print('Scale must be a power of 2!')
		exit(1)
	doubles = int(doubles)

	png_to_waifu2x.gpu = args.gpu

	if args.cpu == 0:
		args.cpu = cpu_count()
	if args.cpu != 1:
		if args.gpu > -1:
			print('WARNING: GPU and Multiprocessing dont get along! Might run out of memory and crash!')
		# Avoid issues with chainer/cupy when multiprocessing: https://github.com/chainer/chainer/issues/2962
		import multiprocessing as mp
		mp.set_start_method('spawn')

	dir_path = hires(chains, path=args.path, scale=args.scale, cpu=args.cpu)
	if not args.nopk3:
		pk3_path = join('out', split(dir_path)[-1] + '.pk3')
		mkzip(pk3_path, dir_path)
		print('Generated: ' + pk3_path)
