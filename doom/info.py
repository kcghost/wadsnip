#!/usr/bin/env python3
# Parse and manipulate iwadinfo lumps
from collections import OrderedDict, Callable
import re
import io
import struct

class DefaultOrderedDict(OrderedDict):
	# Source: http://stackoverflow.com/a/6190500/562769
	def __init__(self, default_factory=None, *a, **kw):
		if (default_factory is not None and not isinstance(default_factory, Callable)):
			raise TypeError('first argument must be callable')
		OrderedDict.__init__(self, *a, **kw)
		self.default_factory = default_factory

	def __getitem__(self, key):
		try:
			return OrderedDict.__getitem__(self, key)
		except KeyError:
			return self.__missing__(key)

	def __missing__(self, key):
		if self.default_factory is None:
			raise KeyError(key)
		self[key] = value = self.default_factory()
		return value

	def __reduce__(self):
		if self.default_factory is None:
			args = tuple()
		else:
			args = self.default_factory,
		return type(self), args, None, None, self.items()

	def copy(self):
		return self.__copy__()

	def __copy__(self):
		return type(self)(self.default_factory, self)

	def __deepcopy__(self, memo):
		import copy
		return type(self)(self.default_factory, copy.deepcopy(self.items()))

	def __repr__(self):
		return 'OrderedDefaultDict(%s, %s)' % (self.default_factory, OrderedDict.__repr__(self))

# https://stackoverflow.com/questions/241327/python-snippet-to-remove-c-and-c-comments
def comment_remover(text):
	def replacer(match):
		s = match.group(0)
		if s.startswith('/'):
			return " " # note: a space and not an empty string
		else:
			return s
	pattern = re.compile(
		r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
		re.DOTALL | re.MULTILINE
	)
	return re.sub(pattern, replacer, text)

class Gzinfo:
	def __init__(self, lump):
		if isinstance(lump, str):
			self.parsed = self.parse(lump)
		elif isinstance(lump, dict):
			self.parsed = lump
		elif isinstance(lump, list):
			if isinstance(lump[0], str):
				self.parsed = self.parse('\n'.join(lump))
			else:
				self.parsed = self.parse('\n'.join([a.decode('utf-8') for a in lump]))
		else:
			self.parsed = self.parse(lump.decode('utf-8'))
	
	def __str__(self):
		return self.unparse(self.parsed).strip()
	
	def __getitem__(self, key):
		return self.parsed[key]
	
	def __setitem__(self, key, value):
		self.parsed[key] = value

	def unparse(self, parsed, tablevel=0):
		string = ''
		if isinstance(parsed, dict):
			for key, value in parsed.items():
				if isinstance(value, list):
					if len(value) > 0 and isinstance(value[0], dict):
						for entry in value:
							string += '\t' * tablevel + key
							string += '\t' * tablevel + ' ' + ' '.join(entry['args'])
							string += '\t' * tablevel + '\n{\n'
							string += '\t' * tablevel + self.unparse(entry, tablevel=tablevel+1)
							string += '\t' * tablevel + '}\n\n'
					elif tablevel is 0: # handle top-level string list
						string += key
						string += '\n{\n'
						for entry in value:
							string += '\t"' + entry + '"\n'
						string += '}\n\n'
					elif key != 'args':
						string += '\t' * tablevel + key + ' = '
						for entry in value:
							if isinstance(entry, str):
								string += '"' + entry + '", '
							elif isinstance(entry, int):
								string += str(entry) + ', '
						string = string[:-2] # Remove last ', '
						string += '\n'
				elif isinstance(value, str):
					string += '\t' * tablevel + key + ' = "' + value + '"\n'
				elif isinstance(value, int):
					string += '\t' * tablevel + key + ' = ' + str(value) + '\n'
		return string
		
	# Parse raw text from iwadinfo/mapinfo
	def parse(self, text):
		parsed = DefaultOrderedDict(lambda: [])
		text = [line.strip() for line in comment_remover(text).splitlines() if line.strip()]
		while text:
			if len(text) > 1 and text[1] == '{':
				subtext = ''
				while text[2] != '}':
					subtext += text.pop(2) + '\n'
				text.pop(2)
				text.pop(1)
				
				args = text[0].split(' ')
				proptype = args.pop(0)
				
				subthing = self.parse(subtext)
				if isinstance(subthing, dict):
					if args:
						subthing['args'] = args
					parsed[proptype].append(subthing)
				else:
					parsed[proptype] = subthing
			elif '=' in text[0]:
				name = text[0].split('=')[0].strip()
				value = text[0].split('=')[1].strip()
				while value[-1] == ',':
					value += text.pop(1)
				if ',' in value:
					entries = []
					for entry in value.split(','):
						if '"' in entry:
							entries.append(entry.strip().strip('"'))
						else:
							entries.append(int(entry.strip()))
					parsed[name] = entries
				else:
					if '"' in value:
						parsed[name] = value.strip('"')
					else:
						parsed[name] = int(value)
			elif text[0][0] == '"':
				# List of quoted values encountered, use a list rather than a dict
				if not isinstance(parsed, list):
					parsed = []
				parsed.append(text[0].strip('"'))
			text.pop(0)
		return parsed

class Iwadinfo(Gzinfo):
	def identify(self, wadname, has_lump):
		for iwad in self.parsed['IWad']:
			if 'MustContain' in iwad:
				if isinstance(iwad['MustContain'], list):
					if not all(has_lump(name) for name in iwad['MustContain']):
						continue
				else:
					if not has_lump(iwad['MustContain']):
						continue
			return Iwadinfo({'IWad' : [iwad]})
		return None

	# Cut out a couple steps for a single IWad def like an identity
	def __getitem__(self, key):
		if len(self.parsed['IWad']) is 1:
			return self.parsed['IWad'][0][key]
		else:
			return super().__getitem__(key)
	
	def __setitem__(self, key, value):
		if len(self.parsed['IWad']) is 1:
			self.parsed['IWad'][0][key] = value
		else:
			super().__setitem__(key, value)

class Sndinfo(Gzinfo):
	def unparse(self, parsed, tablevel=0):
		string = ''
		# TODO: Actually do the thing
		return string
		
	# Parse raw text from sndinfo: https://zdoom.org/wiki/SNDINFO
	def parse(self, text):
		parsed = DefaultOrderedDict(lambda: [])
		text = [line.strip() for line in comment_remover(text).splitlines() if line.strip()]
		while text:
			line = text[0].split()
			# TODO: Parse all commands. Only parsing for commands referencing lump names for now
			if line[0] == '$playersound':
				parsed[line[3]] = line[4]
			elif line[0][0] != '$':
				parsed[line[0]] = line[1]
			text.pop(0)
		return parsed
	
	def getsndlumps(self):
		return list(set([name for key, name in self.parsed.items()]))

class PNames():
	def __init__(self, data):
		with io.BytesIO(data) as data_io:
			data_io.seek(0)
			self.num_entries = struct.unpack('I', data_io.read(4))[0]
			self.entries = []
			for i in range(self.num_entries):
				self.entries.append(struct.unpack('8s', data_io.read(8))[0].decode('ASCII').rstrip('\0'))
	
	def __iter__(self):
		for entry in self.entries:
			yield entry
	
	def __getitem__(self, key):
		return self.entries[key]
		

# https://zdoom.org/wiki/TEXTURES
# ZDoom TEXTURES format texture info
class TextureInfo(dict):
	def __init__(self, name, width, height, patches, optional=False, namespace='Texture', 
			XScale=1.0, YScale=1.0, Offset=(0, 0), Offset2=(0, 0), WorldPanning=False, NoDecals=False, NullTexture=False):
		self.update(locals())
		del self['self']
	
	def __str__(self):
		if self['optional']:
			s = '{namespace} optional "{name}", {width}, {height}'.format(**self) + '\n{\n'
		else:
			s = '{namespace} "{name}", {width}, {height}'.format(**self) + '\n{\n'
		
		for key, default in [ \
				('XScale', 1.0),
				('YScale', 1.0),
				('Offset', (0, 0)),
				('Offset2', (0, 0)),
				('WorldPanning', False),
				('NoDecals', False),
				('NullTexture', False)]:
			if self[key] != default:
				if isinstance(self[key], bool):
					s += '\t' + key + '\n'
				else:
					s += '\t' + key + ' ' + str(self[key]).strip('()') + '\n'
		
		for patch in self['patches']:
			for line in str(patch).split('\n'):
				if line.strip():
					s += '\t' + line + '\n'
		s += '}\n'
		return s

	def __lt__(self, other):
		return (self['namespace'].lower(), self['name'].lower()) < (other['namespace'].lower(), other['name'].lower())

#	def from_string(text):
#		text = [line.strip().strip('"').lower() for line in comment_remover(text).splitlines() if line.strip()]
#		
#		first = text.pop(0)
#		tokens = first.split(',')
#		if len(tokens) != 3:
#			raise Exception('Unexpected Texture format!')
#		firstoken = tokens[0].split()
#		namespace = firstoken[0].strip().capitalize()
#		if firstoken[1] == 'optional':
#			optional = True
#			name = firstoken[2].strip().upper()
#		else:
#			optional = False
#			name = firstoken[1].strip().upper()
#
#		patches = []
#		while text:
#			if text[0].split()[0] in ['patch', 'graphic', 'sprite']:
#				patch = text.pop(0)
#				if '{' in text[0]:
#					while '}' not in text[0]:
#						patch += text.pop(0)
#					patch += text.pop(0)
#				patches.append(PatchInfo.from_string(patch))
#			elif text[0].split()[0] in ['xscale', ]


# ZDoom TEXTURES format patch info
class PatchInfo(dict):
	def __init__(self, name, xorigin, yorigin, namespace='Patch', # Patch, Graphic, Sprite
			FlipX=False, FlipY=False, UseOffsets=False, Rotate=0, Translation='', 
			Colormap=None, Blend=None, Alpha=1.0, Style=''):
		self.update(locals())
		del self['self']
	
	def __str__(self):
		s = '{namespace} "{name}", {xorigin}, {yorigin}'.format(**self)
		started_options = False
		for key, default in [
				('FlipX', False),
				('FlipY', False),
				('UseOffsets', False),
				('Rotate', 0),
				('Translation', ''),
				('Colormap', None),
				('Blend', None),
				('Alpha', 1.0),
				('Style', '')]:
			if self[key] != default:
				if not started_options:
					started_options = True
					s += '\n{\n'
				s += '\t' + key + ' ' + str(self[key]).strip('()') + '\n'
		if started_options:
			s += '}'
		s += '\n'
		return s

class TextureXSanity(Exception):
	pass

# TODO: Support 'NullTexture'
class TextureX():
	def __init__(self, texture_lumps, pnames, hacks=False):
		self.pnames = pnames
		self.textures = []
		
		for texture_lump in texture_lumps:
			if not texture_lump:
				continue
			data_io = io.BytesIO(texture_lump)

			if hacks:
				import hashlib
				lump_hash = hashlib.md5(texture_lump).hexdigest()

			numtextures = struct.unpack('i', data_io.read(4))[0]
			texture_offsets = []
			for i in range(numtextures):
				texture_offsets.append(struct.unpack('i', data_io.read(4))[0])
			
			# First test for strife format (skips unused columndirectory, stepdir and colormap)
			# GZDoom does a different test here which I don't think is a great test.
			# Instead make sure the total size makes sense for either format.
			data_io.seek(texture_offsets[-1] + 0x10)
			strife_patchcount = struct.unpack('h', data_io.read(2))[0]
			data_io.seek(texture_offsets[-1] + 0x14)
			doom_patchcount = struct.unpack('h', data_io.read(2))[0]
			strife_format = False
			if (texture_offsets[-1] + 0x12 + strife_patchcount * 6) == len(texture_lump):
				strife_format = True
			elif (texture_offsets[-1] + 0x16 + doom_patchcount * 10) != len(texture_lump):
				raise TextureXSanity('Total size does not make sense for either Doom or Strife format!')
			
			for texture_offset in texture_offsets:
				data_io.seek(texture_offset)
				
				texture = {
					'name'   : struct.unpack('8s', data_io.read(8))[0].decode('ASCII').rstrip('\0'),
					# Zdoom extended format - uses 'masked' 4 byte value to represent flags, scalex, and scaley
					'flags'  : bool(struct.unpack('H', data_io.read(2))[0]),
					'scalex' : struct.unpack('B', data_io.read(1))[0],
					'scaley' : struct.unpack('B', data_io.read(1))[0],
					'width'  : struct.unpack('h', data_io.read(2))[0], # Wiki says this is signed for some reason?
					'height' : struct.unpack('h', data_io.read(2))[0],
				}

				if not strife_format:
					# unused, but parse it anyway
					texture['columndirectory'] = []
					for i in range(4):
						texture['columndirectory'].append(struct.unpack('B', data_io.read(1))[0])
				
				patchcount = struct.unpack('h', data_io.read(2))[0]
				patches = []
				for i in range(patchcount):
					patch = {
						'originx' : struct.unpack('h', data_io.read(2))[0],
						'originy' : struct.unpack('h', data_io.read(2))[0],
						'patch'   : struct.unpack('h', data_io.read(2))[0],
					}
					
					if not strife_format:
						# unused, but parse it anyway
						patch['stepdir']  = struct.unpack('h', data_io.read(2))[0]
						patch['colormap'] = struct.unpack('h', data_io.read(2))[0]
					patches.append(patch)
				texture['patches'] = patches
				
				# Equivalent of FMultipatchTextureBuilder::CheckForHacks()
				if hacks:
					if lump_hash == '9f4957d0d57ff1eeb3f398ce78b29af9': # TEXTURE1 doom.wad
						if texture['name'] == 'SKY1':
							texture['patches'][0]['originy'] = 0 # Originally -8
					if lump_hash in ['504034fe4f64d013d116ceb6c30f4d57','3cb230c3e9adaeea06f5e8160d06e17b']: # TEXTURE2 doom, doomu
						if texture['name'] == 'BIGDOOR7':
							# In Doom Registered / Ultimate BIGDOOR7 is (-4,-4),(124,-4). This results in a render problem in ZDoom, but by luck/glitch it renders right in Vanilla Doom
							texture['patches'][0]['originy'] = 0 # Originally -4
							texture['patches'][1]['originy'] = 0 # Originally -4
					if lump_hash in ['5698887560a77c74446f9c4a112dc48b', '96f1a941ac536ff2c224b3383902fcb6', '0f03e07e0a2d52703dbf6717633fa64d']: # TEXTURE1 doom2, tnt, plutonia
						if texture['name'] == 'BIGDOOR7':
							# Doom 2 doesn't have the originy problem Doom 1 does. But it does change to (-5, 0),(123, 0).
							# That makes the texture annoyingly slightly different than Doom 1, and a little off center for no good known reason.
							# The texture can't be perfectly center though. Apparently demons can't hang skulls on center, nor their doors perfectly well. No rulers in hell.
							texture['patches'][0]['originx'] = -4 # Originally -5
							texture['patches'][1]['originx'] = 124 # Originally 123
				
				self.textures.append(texture)
			data_io.close()
	
	# convert to populated full ZDoom format
	def to_TextureInfo(self, texture):
		patches = []
		for patch in texture['patches']:
			patch_name = self.pnames[patch['patch']]
			patches.append(PatchInfo(patch_name, patch['originx'], patch['originy']))
		return TextureInfo(texture['name'], texture['width'], texture['height'], patches,
			XScale = texture['scalex'] / 8 if texture['scalex'] else 1.0,
			YScale = texture['scaley'] / 8 if texture['scaley'] else 1.0,
			WorldPanning = bool(texture['flags'] & 0x8000),
			namespace = 'WallTexture')

	def __iter__(self):
		for texture in self.textures:
			yield self.to_TextureInfo(texture)

	def __getitem__(self, key):
		if isinstance(key, str):
			for texture in self.textures:
				if texture['name'] == key:
					return self.to_TextureInfo(texture)
		return self.to_TextureInfo(self.textures[key])
	
	def __str__(self):
		s = ''
		for texture in self:
			s += str(texture) + '\n'
		return s

class Palette():
	def __init__(self, data):
		num_palettes = int(len(data) / (256 * 3))
		data_io = io.BytesIO(data)
		self.palettes = []
		for palette_index in range(num_palettes):
			palette = []
			for color_index in range(256):
				palette.append(struct.unpack('BBB', data_io.read(3)))
			self.palettes.append(palette)
		data_io.close()

	# Default to 'normal' palette
	def __getitem__(self, key):
		return self.palettes[0][key]
