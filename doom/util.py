# Common and utility functions, only do imports in the functions themselves

def cache_data(func):
	import hashlib
	import os

	def wrapper(*data_args):
		m = hashlib.md5()
		for data_arg in data_args:
			try:
				m.update(data_arg)
			except TypeError:
				if hasattr(data_arg, '__dict__') and data_arg.__dict__:
					m.update(repr(data_arg.__dict__).encode())
				else:
					m.update(repr(data_arg).encode())
		checksum = m.hexdigest()
		#print(checksum)
		#return b''
		path = os.path.join('_cache', checksum + '_' + func.__name__)
		try:
			with open(path, 'rb') as fh:
				if func.__name__ in cache_data.invalidate:
					print('Invalidating cache: ' + path)
					raise FileNotFoundError
				return fh.read()
		except FileNotFoundError:
			os.makedirs('_cache', exist_ok=True)
			data = func(*data_args)
			with open(path, 'wb') as fh:
				fh.write(data)
			return data
	return wrapper
# Append to this list the name of any function that is being actively tweaked so old cache data doesn't get used
cache_data.invalidate = []

def save_data(data, path):
	import os
	dirpath = os.path.dirname(path)
	if dirpath:
		os.makedirs(dirpath, exist_ok=True)
	with open(path, 'wb') as fh:
		fh.write(data)

def load_data(path):
	with open(path, 'rb') as fh:
		return fh.read()

def id_iwad(gzdoom, iwad):
	from os.path import basename
	from doom.info import Iwadinfo
	iwad_ref = Iwadinfo(gzdoom['iwadinfo'])
	if not iwad.has_lump('iwadinfo'):
		iwad_id = iwad_ref.identify(basename(iwad.path), lambda lump_name : iwad.has_lump(lump_name))
	else:
		iwad_id = Iwadinfo(iwad['iwadinfo'])
	return iwad_id

# https://stackoverflow.com/questions/20656135/python-deep-merge-dictionary-data
def merge_dict(source, destination):
	for key, value in source.items():
		if isinstance(value, dict):
			# get node or create one
			node = destination.setdefault(key, {})
			merge_dict(value, node)
		else:
			destination[key] = value

	return destination

def chain_args(parser):
	parser.add_argument(
	'-gzdoom',
	help='Specify a gzdoom.pk3 to use. Will search for it in likely places if omitted.')
	parser.add_argument(
	'-iwad',
	action='append',
	nargs='+',
	metavar=('IWAD', 'PWAD'),
	help='Specify IWAD archive, with additional arguments as PWADs to it. (Can be IPK3/PK3 as well, not just wads) Can be used multiple times for filtering/merging commands.')

def get_chains(args):
	from os.path import isfile
	from doom.archive import get_archive
	
	# TODO: Find GZDoom more intelligently in a cross-platform way
	if not args.gzdoom:
		if isfile('iwads/gzdoom.pk3'):
			args.gzdoom = 'iwads/gzdoom.pk3'
		else:
			print('Cannot find a gzdoom.pk3!')
			exit(1)

	chains = []
	for chain_paths in args.iwad:
		# Need a new gzdoom for each chain to do filtering
		# TODO: Could probably do this without copies.
		chain = [get_archive(args.gzdoom)]
		for path in chain_paths:
			chain.append(get_archive(path))
		iwad_id = id_iwad(chain[0], chain[1])
		print('IWAD identified as "' + iwad_id['Name'] + '"')
		for i in range(len(chain)):
			chain[i].gametype = iwad_id['Game'].lower()
			chain[i].game = iwad_id['Autoname'].lower()
		chains.append(chain)
	return chains

def commonize_filters(old, new):
	old = old.split('.')
	new = new.split('.')
	common = ''
	i = 0
	try:
		while old[i] == new[i]:
			common += old[i] + '.'
			i += 1
	except IndexError:
		pass
	return common[:-1]

# https://stackoverflow.com/questions/1855095/how-to-create-a-zip-archive-of-a-directory
# TODO: Support true 7zip?
# TODO: Make thread safe? Don't like chdir
def mkzip(zip_path, dir_path, exclude=[], method='stored'):
	import zipfile
	from os import walk, chdir, getcwd
	from os.path import join, abspath, relpath

	method = method.lower()
	if method.startswith('store'):
		method = zipfile.ZIP_STORED
	elif method.startswith('deflate'):
		method = zipfile.ZIP_DEFLATED
	elif method.startswith('bzip2'):
		method = zipfile.ZIP_BZIP2
	elif method.startswith('lzma'):
		method = zipfile.ZIP_LZMA
	else:
		raise Exception('Not a supported zip method!')

	zip_path = abspath(zip_path)
	dir_path = abspath(dir_path)
	oldcd = getcwd()
	chdir(dir_path)
	dir_path = relpath(dir_path)
	
	zipf = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)
	for root, dirs, files in walk(dir_path):
		# https://stackoverflow.com/questions/19859840/excluding-directories-in-os-walk
		dirs[:] = [d for d in dirs if d not in exclude]
		for file in files:
			zipf.write(join(root, file))
	zipf.close()

	chdir(oldcd)

# Yield textureinfos for 'final' view of textures. Skips sprites, graphics, flats that are overidden by textures or replaced by hires.
# TODO: Add filter from arhive
# TODO: Parse TEXTURES lump
def gen_textures(archive, palette, with_noncomposites=False, with_data=True, to_png=True, hacks=True):
	from doom.graphic import ZImage, texture_to_png, lump_to_png
	from doom.info import TextureX, PNames, TextureInfo
	from copy import deepcopy
	
	if with_noncomposites:
		namespaces = archive.namespaces()
		# Find duplicates in sprites, which can happen by way of the mirror system (e.g. A2A8 when A2 and A8 exist)
		for name in list(namespaces['sprites']):
			if len(name) > 6:
				standard = name[0:6]
				mirrored = name[0:4] + name[6:]
				# There are some more possibilities here, but unlikely and using the mirror texture sounds like a decent default
				if standard in namespaces['sprites'] and mirrored in namespaces['sprites']:
					del namespaces['sprites'][name]

		for namespace in ['sprites', 'graphics', 'flats', 'textures', 'hires']:
			for name, header in namespaces[namespace].items():
				XScale = 1.0
				YScale = 1.0
				offset = (0, 0)
				data = header['get_data']()
				try:
					zimg = ZImage(data, palette, convert=False)
				except:
					print(f'Could not identify {name} as an image (likely a PIL limitation). Skipping.')
					continue
				width = zimg.width
				height = zimg.height
				# TODO: Do Textures get worldpanning by default?
				# TODO: What is offset2, do I need to worry about it?
				# If a hires is still here (didn't replace anything), treat it as a texture
				ttype = namespace[:-1].title().replace('Hire','Texture')
				if zimg.leftoffset != None:
					offset = (zimg.leftoffset, zimg.topoffset)

				if namespace in ['sprites', 'graphics', 'flats']:
					if name in namespaces['textures']:
						# Overidden by a texture, just wait for the texture
						continue
					elif name in namespaces['hires']:
						zimg_hi = ZImage(namespaces['hires'][name]['get_data'](), convert=False)
						width = zimg_hi.width
						height = zimg_hi.height
						XScale = zimg_hi.width / zimg.width
						YScale = zimg_hi.height / zimg.height
						leftoffset = int(zimg.leftoffset * XScale)
						topoffset = int(zimg.topoffset * YScale)
						offset = (leftoffset, topoffset)
						if with_data:
							data = namespaces['hires'][name]['data']
						# Delete it so it doesn't get reprocessed as a texture
						# Note this means only one lump can be replaced, which is slightly different than in GZDoom that replaces all of same name
						# regardless of namespace (though I think that is buggy/unexpected behavior)
						del namespaces['hires'][name]

				# A texture without patches
				texture = TextureInfo(name.upper(), width, height, [], namespace=ttype, Offset=offset, XScale=XScale, YScale=YScale)
				if with_data:
					texture['data'] = data
					if to_png:
						texture['data'] = lump_to_png(data, palette)

				yield texture

	if archive.has_lump('texture1') and archive.has_lump('pnames'):
		pnames = PNames(archive['pnames'])
		for texture in TextureX([archive['texture1'], archive['texture2']], pnames, hacks=hacks):
			if with_data:
				for i in range(len(texture['patches'])):
					texture['patches'][i]['data'] = archive[texture['patches'][i]['name']]
				if to_png:
					texture['data'] = texture_to_png(texture, palette)
			yield texture
	if archive.has_lump('textures'):
		pass

# Take list of namespaces representing the same namespace, e.g. 'sprites' from differing IWADS
# and consolidate them using their filters.
# Detect duplicates and commonize their filters.
# Returns list of filtered headers
def filter_namespace(namespaces):
	import hashlib
	names = set()
	for namespace in namespaces:
		for name in namespace:
			names.add(name)
	names = list(names)
	names.sort()

	filtered = []
	for name in names:
		headers = [namespace[name] for namespace in namespaces if name in namespace]
		if len(headers) > 1:
			by_csum = {}
			for header in headers:
				csum = hashlib.md5(header['data']).hexdigest()
				if csum not in by_csum:
					by_csum[csum] = []
				by_csum[csum].append(header)

			by_val = list(by_csum.values())
			by_val.sort(key=len, reverse=True)
			filters = []
			for dups in by_val:
				if len(dups) == 1:
					filtered.append(dups[0])
				else:
					filt = dups[0]['filter']
					for dup in dups[1:]:
						filt = commonize_filters(filt, dup['filter'])

					if filt not in filters:
						filters.append(filt)
						dups[0]['filter'] = filt
						filtered.append(dups[0])
					else:
						for dup in dups:
							filtered.append(dup)
		else:
			filtered.append(headers[0])
	return filtered

# Take lists of headers belonging to the same namespace, e.g. 'patches' from two different IWADs
# and consolidate them using a renaming scheme
# Returns namespace
def rename_namespace():
	pass

def extract(chain, path=None, with_iwad=False, modernize=False):
	from os.path import basename, splitext, join
	from shutil import rmtree
	from doom.archive import Archives
	if modernize:
		from doom.graphic import lump_to_png, texture_to_png
		from doom.sound import lump_to_sound
		from doom.info import Palette, PNames, TextureX
	
	pwad_only = False
	if len(chain) > 2 and not with_iwad:
		index = 2
		pwad_only = True
	else:
		index = 1
	
	archive = Archives(*chain[index:])
	full = Archives(*chain)
	palette = None
	try:
		palette = Palette(full['playpal'])
	except:
		pass
	
	if not path:
		names = ''
		for archive in chain[index:]:
			names += splitext(basename(archive.path))[0] + '_'
		names = names[:-1]
		path = join('out', names + '_modernized' if modernize else names + '_extracted')
	rmtree(path, ignore_errors=True)
	
	for header in archive:
		if modernize:
			# Handled as a group, convert to TEXTURES
			if header['name'].lower() in ['texture1', 'texture2', 'pnames']:
				continue
			
			if palette and header['extension'] != 'png' and header['namespace'] in ['sprites', 'graphics', 'patches', 'flats', 'textures', 'hires']:
				try:
					header['data'] = lump_to_png(header['data'], palette)
					header['extension'] = 'png'
				except:
					print(f'Could not identify {header["name"]} as an image (likely a PIL limitation). Skipping.')
			if header['extension'] == 'lmp' and header['namespace'] in ['sounds']:
				header['data'] = lump_to_sound(header['data'], fmt='flac', skip_pc=False)
				header['extension'] = 'flac'

		extension = '.' + header['extension'] if header['extension'] else ''
		save_data(header['data'], join(path, header['namespace'] if header['namespace'] != 'global' else '', header['name'].lower() + extension))
	
	if modernize:
		# No hacks cause I think even a semi-accurate 'extraction' should be warts and all
		textures_str = ''
		for texture in gen_textures(archive, palette, hacks=False):
			save_data(texture_to_png(texture, palette), join(path, 'composite', texture['namespace'].lower() + 's', texture['name'].lower() + '.png'))
			textures_str += str(texture) + '\n'
		# Include rebuilt TEXTURES lump if TEXTUREX was used in any capacity
		if archive.has_lump('texture1') and archive.has_lump('pnames'):
			save_data(textures_str.encode(), join(path, 'textures.txt'))
		# The other way to 'modernize' might be to forego a textures lump entirely and use the 'textures' directory
		# But since textures is an 'override' namespace that affects sprites, graphics, etc., it becomes a nightmare of name-related edge cases.
		# For example STEP1 walltexture placed in textures will override the STEP1 flat in flats.
		# It would be better if ZDoom introduced a 'walltextures' namespace to resolve these problems.
	
	if modernize and not pwad_only:
		iwad_id = id_iwad(chain[0], chain[1])
		# Must have a unique name, https://forum.zdoom.org/viewtopic.php?f=3&t=57835
		iwad_id['Name'] = iwad_id['Name'] + ' Modernized'
		save_data(str(iwad_id).encode(), join(path, 'iwadinfo.txt'))

	print('Extracted to: ' + path)
	return path


def pool_init(l, gpu):
	from doom.graphic import png_to_waifu2x
	global lock
	lock = l
	png_to_waifu2x.gpu = gpu

def pool_lock():
	try:
		lock.acquire()
	except:
		pass

def pool_unlock():
	try:
		lock.release()
	except:
		pass

# TODO: Support scaling gzdoom resources as well
def hires(chains, path=None, scale=2, cpu=1):
	from os.path import basename, splitext, join
	from shutil import rmtree
	from doom.archive import Archives
	from doom.graphic import  superscale, png_to_waifu2x
	from doom.info import Palette, PatchInfo
	
	if not path:
		names = ''
		for chain in chains:
			for archive in chain[1:]:
				names += splitext(basename(archive.path))[0] + '_'
		names = names[:-1]
		path = join('out', names + '_hires[' + str(scale) + 'x]')
	rmtree(path, ignore_errors=True)
	
	all_namespaces = []
	for chain in chains:
		print('Processing: ' + chain[0].game)
		archive = Archives(*chain[1:])
		palette = Palette(archive['playpal'])
		
		namespaced = {ns:{} for ns in ['Sprite', 'Graphic', 'Flat', 'WallTexture', 'Texture']}
		# Get all the data at once for filtering. To PNG as well, since it seems Doom graphics between Doom 1/2 can be different yet render to the same image.
		for texture in gen_textures(archive, palette, with_noncomposites=True, with_data=True, to_png=True, hacks=True):
			texture['filter'] = chain[0].game
			texture['scale'] = scale
			namespaced[texture['namespace']][texture['name']] = texture
		all_namespaces.append(namespaced)

	to_scale = []
	for ns_name in ['Sprite', 'Graphic', 'Flat', 'WallTexture', 'Texture']:
		print('Filtering...')
		to_scale += filter_namespace([gr_ns[ns_name] for gr_ns in all_namespaces])

	textures = []
	def post_scale(texture):
		patch_paths = ('patches', texture['namespace'].lower() + 's', texture['name'].replace('\\','^').lower() + '.png')
		save_data(texture['data'], join(path, 'filter', texture['filter'], *patch_paths))
		texture['patches'] = [PatchInfo('/'.join(patch_paths), 0, 0)]
		# Try to save memory
		del texture['data']
		textures.append(texture)

	if scale > 1 and cpu > 1:
		# https://stackoverflow.com/questions/25557686/python-sharing-a-lock-between-processes
		from multiprocessing import Pool, Lock
		l = Lock()
		pool = Pool(processes=cpu, initializer=pool_init, initargs=(l,png_to_waifu2x.gpu))
		for texture in pool.imap_unordered(superscale, to_scale):
			post_scale(texture)
	else:
		for texture in to_scale:
			if scale > 1:
				# TODO: superscale should modify width, height, adjust offsets, etc.
				texture = superscale(texture)
			post_scale(texture)

	# TODO: Generate texture definitions per IWAD with this list
	textures.sort()
	for chain in chains:
		gametextures = {ns:{} for ns in ['Sprite', 'Graphic', 'Flat', 'WallTexture', 'Texture']}
		for texture in textures:
			if not chain[0].game.startswith(texture['filter']):
				continue
			name = texture['name']
			ns = texture['namespace']
			if name in gametextures[ns]:
				# Give priority to entries that are closer to the actual filter
				if texture['filter'] < gametextures[ns][name]['filter']:
					continue
			gametextures[ns][name] = texture
		gametextures = [texture for ns in gametextures.keys() for texture in gametextures[ns].values()]
		gametextures.sort()
		texturedef = ''
		for texture in gametextures:
			texturedef += str(texture) + '\n'
		save_data(texturedef.encode(), join(path, 'filter', chain[0].game, 'textures.hires'))
	
	print('Extracted to: ' + path)
	return path
	
# Replace the normal sounds with "rendered" PC speaker ones
def bleeps(chains, path=None):
	from os.path import basename, splitext, join
	from shutil import rmtree
	from difflib import get_close_matches
	from doom.archive import Archives
	from doom.sound import Dmx, dmx_to_ogg
	
	if not path:
		names = ''
		for chain in chains:
			for archive in chain[1:]:
				names += splitext(basename(archive.path))[0] + '_'
		names = names[:-1]
		path = join('out', names + '_bleeps')
	rmtree(path, ignore_errors=True)
	
	all_namespaces = []
	for chain in chains:
		print('Processing: ' + chain[0].game)
		archive = Archives(*chain[1:])
		
		sound_ns = {}
		pc_names = []
		dig_names = []
		for header in archive:
			if header['extension'] == 'lmp' and header['namespace'] in ['sounds']:
				sound = Dmx(header['data'])
				if sound.is_pc():
					header['data'] = dmx_to_ogg(header['data'])
					header['extension'] = 'ogg'
					sound_ns[header['name']] =  header
					pc_names.append(header['name'])
				else:
					dig_names.append(header['name'])

		# Find digital name equivalents
		for pc_name in set(pc_names):
			matches = get_close_matches(pc_name, dig_names)
			# if no match just skip
			if not matches:
				print(f'Can\'t find a digital name match for {pc_name}. Skipping.')
				sound_ns.pop(pc_name)
			else:
				name = matches[0]
				sound_ns[name] = sound_ns.pop(pc_name)
				sound_ns[name]['name'] = name

		all_namespaces.append(sound_ns)

	filtered = filter_namespace(all_namespaces)
	for header in filtered:
		save_data(header['data'], join(path, 'filter', header['filter'], 'sounds', header['name'].lower() + '.' + header['extension']))

	print('Extracted to: ' + path)
	return path
