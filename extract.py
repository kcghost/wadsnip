#!/usr/bin/env python3

if __name__ == '__main__':
	import argparse
	from os.path import split, join, isfile
	from doom.util import chain_args, get_chains, mkzip, extract

	parser = argparse.ArgumentParser(
		description='Extract a WAD or PK3, extracts all chains in order. '
		'By default if one or more PWADs are specified it will just extract those. If just an IWAD is specified it will just extract that. '
		'Note that if more than one archive is specified later files will overwrite the earlier ones. '
		'Within the extracted directory a folder called "composite" will contain rendered composite textures. '
		'A conglomerate PK3 will also be created (without "composite"), and if the IWAD is included (and modernize is enabled) it will be a standalone runnable IPK3.'
	)
	chain_args(parser)
	parser.add_argument(
		'--with-iwad',
		action='store_true',
		help='Include the IWAD in the extraction when PWADs are specified.',
	)
	parser.add_argument(
		'--modernize',
		action='store_true',
		help='Convert as many formats as possible into modern and readable equivalents. Also support creating a standalone IPK3.',
	)
	parser.add_argument(
		'-path',
		help='Directory to extract files to. Also determines name and location of PK3.'
	)
	args = parser.parse_args()
	chains = get_chains(args)

	for chain in chains:
		dir_path = extract(chain, path=args.path, with_iwad=args.with_iwad, modernize=args.modernize)

		extension = '.pk3'
		if isfile(join(dir_path, 'iwadinfo.txt')):
			extension = '.ipk3'
		pk3_path = join('out', split(dir_path)[-1] + extension)
		# Don't include composite in pk3, it is only there to demonstrate the rendered textures, not actrually be used in any capacity
		mkzip(pk3_path, dir_path, exclude=['composite'])
		print('Generated: ' + pk3_path)
