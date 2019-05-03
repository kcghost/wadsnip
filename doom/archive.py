# Support several generic methods on wads, pk3, and folders
import zipfile
import struct
import os
import io
from fnmatch import fnmatch
from os import remove

# Execute statement and return default on failure
def default(statement, default_value):
	try:
		return exec(statement)
	except:
		return default_value

def get_archive(path):
	if os.path.isfile(path):
		if any(os.path.splitext(path)[1].lower() == extension for extension in ['.wad', '.iwad']):
			return Wad(path)
		elif any(os.path.splitext(path)[1].lower() == extension for extension in ['.zip', '.pk3', '.pkz', '.pke', '.ipk3', '.pk7', '.pkz', '.ipk7']):
			return Pk3(path)
		else:
			raise Exception('Unrecognized file extension!')
	elif os.path.isdir(path):
		return Folder(path)
	else:
		raise Exception('Invalid path!')

# Handles multiple archives at once
class Archives():
	def __init__(self, *archives):
		self.archives = list(archives)
	
	def __add__(self, other):
		# Propagate any filters forward if possible
		other.game = self.game
		other.gametype = self.gametype
		if hasattr(other, 'archives'):
			full_list = self.archives + other.archives
		else:
			full_list = self.archives + [other]
		return Archives(*full_list)
	
	def has_lump(self, name_match='*', namespace_match='*'):
		return any(archive.has_lump(name_match, namespace_match) for archive in self.archives)
	
	def get_lumps(self, name_match='*', namespace_match='*'):
		return [lump for archive in self.archives for lump in archive.get_lumps(name_match, namespace_match)]
	
	def headers(self, name_match='*', namespace_match='*'):
		for archive in self.archives:
			for header in archive.headers(name_match, namespace_match):
				yield header
	
	def namespaces(self):
		from doom.util import merge_dict
		namespaces = {}
		# Later archives should override earlier ones
		for archive in self.archives:
			namespaces = merge_dict(archive.namespaces(), namespaces)
		return namespaces
	
	# Loop over all headers, including overridden
	def __iter__(self):
		for archive in self.archives:
			for header in archive:
				yield header
	
	def __getitem__(self, key):
		# Last archive takes priority as far as overrides
		for archive in reversed(self.archives):
			data = archive[key]
			if data:
				return data
		return None

class Archive():
	def has_lump(self, name_match='*', namespace_match='*'):
		return len(self.get_lump_headers(name_match, namespace_match)) > 0
	
	def get_lumps(self, name_match='*', namespace_match='*'):
		return [lump['data'] for lump in self.get_lump_headers(name_match, namespace_match, with_data=True)]

	def headers(self, name_match='*', namespace_match='*'):
		# https://eev.ee/blog/2011/04/24/gotcha-python-scoping-closures/
		def get_data_f(handle):
			def get_data():
				return self.get_data(handle)
			return get_data
		
		for header in self.get_lump_headers(name_match, namespace_match):
			header['get_data'] = get_data_f(header['handle'])
			yield header

	def namespaces(self):
		# Get last header (not overridden) for each namespace
		# TODO: Add special cases for types like TEXTURES.wood that don't get overridden with different extensions
		namespaces = {
			'acs'           :{},
			'colormaps'     :{},
			'flats'         :{},
			'graphics'      :{},
			'hires'         :{},
			'maps'          :{},
			'music'         :{},
			'patches'       :{},
			'sprites'       :{},
			'sounds'        :{},
			'textures'      :{},
			'voices'        :{},
			'voxels'        :{},
			'global'        :{},
		}
		for namespace in namespaces:
			for header in self.headers(namespace_match=namespace):
				namespaces[namespace][header['name']] = header
		return namespaces

	def __add__(self, other):
		return Archives(self, other)

	def __iter__(self):
		headers = self.get_lump_headers()
		for header in headers:
			header['data'] = self.get_data(header['handle'])
			yield header
	
	# Return last matching in global namespace
	def __getitem__(self, key):
		key = key.lower()
		headers = self.get_lump_headers(name_match = key)
		if headers:
			header = headers[-1]
			return self.get_data(header['handle'])
		return None

# TODO: Implement Folder 'pack'
class Folder(Archive):
	pass

class Pk3(Archive):
	def __init__(self, path):
		self.path = path
		self.file = zipfile.ZipFile(path)
		# For lump filtering
		self.game = None
		self.gametype = None
		self.namelist = self.scan_subarchives(self.file.namelist())

	# TODO: __del__ is shitty and I should find a better way to guarantee the cleanup of tmp files
	def __del__(self):
		if self.subarchives:
			for subarchive in self.subarchives.values():
				remove(subarchive.path)

	def scan_subarchives(self, namelist):
		from os.path import splitext
		from tempfile import mkstemp
		from os import close
		from doom.util import save_data
		
		self.subarchives = {}
		
		outlist = []
		for name in namelist:
			ext = None
			namespace = None
			try:
				ext = splitext(name)[1]
				if name.split('/')[0] == 'filter':
					namespace = name.split('/')[2]
				else:
					namespace = name.split('/')[0]
			except:
				pass
			
			if namespace != 'maps' and ext in ['.wad', '.iwad', '.zip', '.pk3', '.pkz', '.pke', '.ipk3', '.pk7', '.pkz', '.ipk7']:
				fh, tmpfile = mkstemp()
				close(fh)
				save_data(self.get_data(name), tmpfile)
				if ext in ['.wad', '.iwad']:
					self.subarchives[name] = Wad(tmpfile)
				else:
					self.subarchives[name] = Pk3(tmpfile)
				continue
			outlist.append(name)
		return outlist
	
	def get_lump_headers(self, name_match='*', namespace_match='*', with_data=False):
		headers = []
		for path in self.namelist:
			# TODO: Handle extensions on name match?
			handle = path
			path = path.lower()
			name_match = name_match.lower()
			namespace_match = namespace_match.lower()
			
			if path[-1] == '/':
				continue
			
			name = os.path.splitext(path.split('/')[-1])[0]
			filt = None
			if '/' in path:
				if path.split('/')[0] == 'filter':
					filt = path.split('/')[1]
					if filt.startswith('doom.doom'):
						filt = filt.replace('doom.doom', 'doom.id.doom', 1)
					namespace = path.split('/')[2]
				else:
					namespace = path.split('/')[0]
			else:
				namespace = 'global'
			extension = 'lmp'
			try:
				extension = os.path.splitext(path.split('/')[-1])[1][1:]
			except:
				pass
			
			if not fnmatch(namespace, namespace_match) or not fnmatch(name, name_match):
				continue
			if filt:
				if not self.gametype or filt.startswith('game-') and self.gametype not in filt:
					continue
				elif not self.game or not self.game.startswith(filt):
					continue
			else:
				filt = self.game
			
			headers.append({
				'name': name,
				'namespace': namespace,
				'extension': extension,
				'handle': handle,
				'type': None,
				'filter': filt,
				'data': self.get_data(handle) if with_data else None
			})
		for name, archive in self.subarchives.items():
			archive.game = self.game
			archive.gametype = self.gametype
			subheaders = archive.get_lump_headers(name_match, namespace_match, with_data)
			for i in range(len(subheaders)):
				subheaders[i]['handle'] = (name ,subheaders[i]['handle'])
			headers += subheaders
		return headers
	
	def get_data(self, handle):
		if isinstance(handle, tuple):
			name, subhandle = handle
			return self.subarchives[name].get_data(subhandle)
		lump_file = self.file.open(handle)
		data = lump_file.read() # Only binary read allowed by ZipFile
		lump_file.close()
		return data

class Wad(Archive):
	def __init__(self, path):
		self.path = path
		self.file = open(path, 'rb')
		self.wad_dir, self.is_iwad = self.get_wad_dir()
		self.game = None
		self.gametype = None
		self.get_wad_namespaces()
	
	def __del__(self):
		self.file.close()

	# Return the directory of a wad as a list of tuples (pointer, size, name)
	# https://doomwiki.org/wiki/WAD
	def get_wad_dir(self):
		self.file.seek(0)
		wad_type, num_entries, dir_pointer = struct.unpack('4sii', self.file.read(12))
		wad_type = wad_type.decode('ASCII').rstrip('\0')
		if wad_type != 'IWAD' and wad_type != 'PWAD':
			raise Exception('Not a valid WAD file!')
		is_iwad = True if wad_type == 'IWAD' else False

		self.file.seek(dir_pointer)
		wad_dir = []
		for i in range(num_entries):
			lump_pointer, lump_size, lump_name = struct.unpack('ii8s', self.file.read(16))
			lump_name = lump_name.decode('ASCII').rstrip('\0')
			wad_dir.append((lump_pointer, lump_size, lump_name))
		return wad_dir, is_iwad
	
	# Return headers to matching lumps, */* returns headers for all lumps
	def get_lump_headers(self, name_match='*', namespace_match='*', with_data=False):
		headers = []
		for namespace in self.namespaced:
			if not fnmatch(namespace.split('_')[0], namespace_match):
				continue
			if not namespace.startswith('maps_'):
				for pointer, size, name in self.namespaced[namespace]:
					if fnmatch(name.lower(), name_match.lower()):
						headers.append({
							'name': name.lower(),
							'namespace': namespace.split('_')[0],
							'extension': 'lmp',
							'type': default("namespace.split('_')[1]", None),
							'handle': (pointer, size, name),
							'filter': self.game,
							'data': self.get_data((pointer, size, name)) if with_data else None
						})
			else:
				for map_dir in self.namespaced[namespace]:
					extension = 'wad' if namespace != 'maps_gwa' else 'gwa'
					if fnmatch(map_dir[0][2].lower(), name_match.lower()):
						headers.append({
							'name': map_dir[0][2].lower(),
							'namespace': namespace.split('_')[0],
							'extension': extension,
							'type': default("namespace.split('_')[1]", None),
							'handle': map_dir,
							'filter': self.game,
							'data': self.get_data(map_dir) if with_data else None
						})
		return headers

	def get_data(self, handle):
		# if map:
		if isinstance(handle, list):
			return self.extract_wad(handle)
		else:
			(pointer, size, name) = handle
			self.file.seek(pointer)
			return self.file.read(size)

	def extract_wad(self, wad_dir, iwad=False):
		wad_type = b'IWAD' if iwad else b'PWAD'
		out_file = io.BytesIO()
		data_size = 0
		for (pointer, size, name) in wad_dir:
			data_size += size
		
		# header
		out_file.write(struct.pack('4sii', wad_type, len(wad_dir), data_size + 12))
		new_dir = []
		# data
		for (pointer, size, name) in wad_dir:
			self.file.seek(pointer)
			new_dir.append((out_file.tell(), size, name))
			out_file.write(self.file.read(size))
		# directory
		for (pointer, size, name) in new_dir:
			out_file.write(struct.pack('ii8s', pointer, size, name.encode()))
		out_file.seek(0)
		wad_bytes = out_file.read()
		out_file.close()
		return wad_bytes

	# https://doomwiki.org/wiki/Lump
	# A list of names that might occur after a 'THINGS' lump for a Doom/Hexen map definition or a port
	# This includes any appended GL nodes, as well as lumps specific to ports and a conventional SCRIPTS lump
	# Once a THINGS lump is found, pop the last entry off the list for the map header.
	# Will consider each node to be part of the map until a lump is found that is not in this list
	# Additionally there are two special names to look for GL_(map name) and SCRIPTS/SCRIPTXX where XX is a map number
	doomhexen_names = [
	'THINGS',
	'LINEDEFS',
	'SIDEDEFS',
	'VERTEXES',
	'SEGS',
	'SSECTORS',
	'NODES',
	'SECTORS',
	'REJECT',
	'BLOCKMAP',
	'BEHAVIOR',
	'LEAFS',
	'LIGHTS',
	'MACROS',
	'GL_LEVEL',
	'GL_VERT',
	'GL_SEGS',
	'GL_SSECT',
	'GL_NODES',
	'GL_PVS',
	'SCRIPT*'
	]

	# A list of names that might occur after a 'GL_VERT' lump
	# GL Nodes can be appended to a map, or on its own in a .GWA PWAD. These names are for detecting on its own.
	# Starts with GL_(mapname) or GL_LEVEL (optional when appended). Also optional 'GL_PVS'.
	gl_names = [
	'GL_LEVEL'
	'GL_SEGS',
	'GL_SSECT',
	'GL_NODES',
	'GL_PVS'
	]
	# UDMF is just map header, then TEXTMAP, then anything until ENDMAP. Unsure about 'additional' lumps in this context, but I assume for now everything should be within the marker.
	# TODO: Support Alpha Doom formats?

	# Default name recognition. TODO: Update based on lumps like SNDINFO or other descriptive information
	known_names = {
		# TODO: Parse SNDINFO
		'sounds_digital': [
			'DS*'
		],
		'sounds_pcspkr': [
			'DP*'
		],
		# TODO: Parse MAPINFO
		'music': [
			'D_*'
		],
		# Mostly taken from omgifol. May not be a complete list.
		# TODO: Parse...I don't even know. 
		'graphics': [
			'TITLEPIC',
			'CWILV*',
			'WI*',
			'M_*',
			'INTERPIC',
			'BRDR*',
			'PFUB?',
			'ST*',
			'VICTORY2',
			'CREDIT',
			'END?',
			'WI*',
			'BOSSBACK',
			'ENDPIC',
			'HELP',
			'BOX??',
			'AMMNUM?',
			'HELP*',
			'DIG*',
			'PRBOOM'
		],
		'patches': [
		],
		# TODO: Assemble a more complete list of 'special' lumps
		'global': [
			'PLAYPAL',
			'COLORMAP',
			'ENDOOM',
			'DEMO*',
			'TEXTURE*',
			'PNAMES',
			'GENMIDI',
			'DMXGUS*',
			'DBIGFONT',
			'DEHACKED'
		]
	}

	# Given a wad directory, attempt to separate lumps into types
	def get_wad_namespaces(self):
		from doom.info import PNames
		from copy import deepcopy
		
		# Group into (mostly) GZDoom namespaces for folder dump.
		# 'global' will act as the root directory, separate out maps, sounds
		# https://zdoom.org/wiki/Using_ZIPs_as_WAD_replacement
		wad_namespaces = {
			'acs'           :[],
			'colormaps'     :[],
			'flats'         :[],
			'graphics'      :[],
			'hires'         :[],
			'maps_doom'     :[],
			'maps_udmf'     :[],
			'maps_gwa'      :[],
			'music'         :[],
			'patches'       :[],
			'sprites'       :[],
			'sounds_digital':[],
			'sounds_pcspkr' :[],
			'textures'      :[],
			'voices'        :[],
			'voxels'        :[],
			'global'        :[],
		}
		
		# https://www.doomworld.com/forum/topic/32737-s_start-and-ss_start-markers/
		# There is a convention to use doubles i.e. SS_START for PWAD additions. Treat doubles as the same as their single letter counterparts
		# https://zdoom.org/wiki/Using_ZIPs_as_WAD_replacement
		marker_groups= {
			'A':  'acs',
			'AA': 'acs',
			'C':  'colormaps',
			'CC': 'colormaps',
			'F':  'flats',
			'FF': 'flats',
			'HI': 'hires',
			'S':  'sprites',
			'SS': 'sprites',
			'P':  'patches',  # Not usually handled by ZDoom, primarily should use PNAMES
			'PP': 'patches',
			'TX': 'textures',
			'V':  'voices',
			'VV': 'voices',
			'VX': 'voxels'
		}
		
		wad_dir = deepcopy(self.wad_dir)
		pnames = None
		while wad_dir:
			# Consume regular Doom/Hexen maps
			if len(wad_dir) > 1 and wad_dir[1][2] == 'THINGS':
				new_map = [wad_dir.pop(0)]
				while any(fnmatch(wad_dir[0][2], pattern) for pattern in self.doomhexen_names):
					new_map.append(wad_dir.pop(0))
				wad_namespaces['maps_doom'].append(new_map)
			# Consume UDMF maps
			elif len(wad_dir) > 1 and wad_dir[1][2] == 'TEXTMAP':
				new_map = [wad_dir.pop(0)]
				while wad_dir[0][2] != 'ENDMAP':
					new_map.append(wad_dir.pop(0))
				new_map.append(wad_dir.pop(0))
				wad_namespaces['maps_udmf'].append(new_map)
			# Consume isolated gl nodes (.gwa)
			elif len(wad_dir) > 1 and wad_dir[1][2] == 'GL_VERT':
				# Either GL_LEVEL or GL_MAPXX
				new_map = [wad_dir.pop(0)]
				while any(fnmatch(wad_dir[0][2], pattern) for pattern in self.gl_names):
					new_map.append(wad_dir.pop(0))
				wad_namespaces['maps_gwa'].append(new_map)
			# TODO: Support alpha doom map format
			# Consume known markers
			elif fnmatch(wad_dir[0][2], '*_START') and wad_dir[0][2].split('_')[0] in marker_groups:
				namespace = wad_namespaces[marker_groups[wad_dir[0][2].split('_')[0]]]
				endmarker = wad_dir[0][2].split('_')[0] + '_END'
				# Don't add the markers themselves to the namespace
				wad_dir.pop(0)
				while wad_dir[0][2] != endmarker:
					if wad_dir[0][1] > 0:
						namespace.append(wad_dir.pop(0))
					else:
						wad_dir.pop(0)
				wad_dir.pop(0)
			# Consume by known name lists
			else:
				for namespace, names in self.known_names.items():
					if any(fnmatch(wad_dir[0][2], pattern) for pattern in self.known_names[namespace]):
						if wad_dir[0][2] == 'PNAMES':
							pnames = PNames(self.get_data(wad_dir[0]))
							self.known_names['patches'] = pnames.entries
						wad_namespaces[namespace].append(wad_dir.pop(0))
						break
				else:
					print('Unrecognized lump \"' + wad_dir[0][2] + '\". Treating as global data.')
					wad_namespaces['global'].append(wad_dir.pop(0))
		
		self.namespaced = wad_namespaces
		# Pick up and duplicate anything used as a patch from PNAMES into the patch namespace
		# This is necessary for textures like SLAD10 from Final Doom, which uses a sprite
		if pnames:
			for pointer, size, name in self.wad_dir:
				if name in pnames:
					# TODO: Won't this double add? Should be a set?
					self.namespaced['patches'].append((pointer, size, name))
