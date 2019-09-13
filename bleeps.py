#!/usr/bin/env python3

if __name__ == '__main__':
	import argparse
	from os.path import split, join
	from doom.util import chain_args, get_chains, mkzip, bleeps

	parser = argparse.ArgumentParser(
		description='Generate a bleeps package (Replace sounds with PC Speaker ones). '
			'Builds appropriate filters for IWAD chains. You may safely use the resulting package with all IWAD/PWAD chains specified.'
	)
	chain_args(parser)
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

	dir_path = bleeps(chains, path=args.path)
	if not args.nopk3:
		pk3_path = join('out', split(dir_path)[-1] + '.pk3')
		mkzip(pk3_path, dir_path)
		print('Generated: ' + pk3_path)
