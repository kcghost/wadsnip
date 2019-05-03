import io
import struct
import os
import sys
from doom.util import cache_data, save_data, load_data
from PIL import Image, ImageOps

@cache_data
def lump_to_png(lump_data, palette):
	return ZImage(lump_data, palette).to_png()

@cache_data
def texture_to_png(textureinfo, palette):
	# TODO: Render all the crazy options correctly instead of simply ignoring them
	img = Image.new('RGBA', (textureinfo['width'], textureinfo['height']), (0, 0, 0, 0))
	
	for patch in textureinfo['patches']:
		patch_img = ZImage(patch['data'], palette)
		img.paste(patch_img, box=(patch['xorigin'], patch['yorigin']), mask=patch_img)
	
	zimg = ZImage(img, palette)
	return zimg.to_png()

# Not caching, because this function could probably be tweaked until the end of time.
# TODO: Perhaps increase the canvas for both xbrz and waifu, and return back a corrected offset - this would necessitate the use of TEXTURES to define all graphics
# Would also run into namepace issues that way
def superscale(texture):
	png_data = texture['data']
	scale = texture['scale']

	# TODO: Increase canvas size for XBRZ, but crop it down to minimum size and keep that size
	texture['XScale'] *= scale
	texture['YScale'] *= scale
	texture['width']  *= scale
	texture['height'] *= scale
	texture['Offset'] = tuple(i * scale for i in texture['Offset'])
	if texture['namespace'].lower() in ['walltexture', 'texture']:
		texture['WorldPanning'] = True

	print('Processing ' + texture['name'].upper())

	# UpResNet10 is slightly blurrier, less weird sharp details. Might be better for wall textures in some instances?
	method = 'ResNet10' 
	# For sprites, just cache scales with as much pixel info as possible, then cut it out with xbrz
	waifu_thresh = 0
	# Arbitrary value to get rid of alpha blending from xbrz. Halfway seems like a reasonable value.
	xbrz_thresh = 128
	
	if has_transparency(png_data):
		# Scale using xbrz, but only to grab its alpha layer to use as a mask on waifu2x
		xbrz_data = xbrz_scale(png_data, scale, xbrz_thresh)
		
		xbrz_img = data_to_image(xbrz_data)
		
		png_data = waifu_scale(png_data, scale, waifu_thresh, method)

		png_img = data_to_image(png_data)
		png_img.putalpha(xbrz_img.split()[-1])
		png_data = image_to_data(png_img)
		texture['data'] = png_data
		return texture
	else:
		png_data = waifu_scale(png_data, scale, waifu_thresh, method)
		texture['data'] = png_data
		return texture

@cache_data
def waifu_scale(png_data, scale, waifu_thresh, method):
	from math import log
	doubles = log(scale, 2)
	if not doubles.is_integer():
		raise Exception('Scale must be a power of 2!')
	doubles = int(doubles)

	for i in range(doubles):
		png_data = png_to_waifu2x(png_data, 'scale', method, 'rgb')
		if waifu_thresh >= 0:
			png_img = data_to_image(png_data)
			png_img = alpha_threshold(png_img, waifu_thresh)
			png_data = image_to_data(png_img)

	return png_data	

@cache_data
def xbrz_scale(xbrz_data, scale, xbrz_thresh):
	# xbrz only allows scaling 2x-6x
	xbrz_scales = {
		2:  [2],
		3:  [3],
		4:  [4],
		5:  [5],
		6:  [6],
		8:  [4,2],
		16: [4,4],
		32: [4,4,2],
		64: [4,4,4]
	}

	# Make the canvas a little bigger before passing to xbrz, better results for sprites that hug the edges of the image.
	xbrz_img = data_to_image(xbrz_data)
	width, height = xbrz_img.size
	border = int(((width + height) / 2) / 10) # Approx. ten percent border
	xbrz_img = ImageOps.expand(xbrz_img, border=border, fill=(0,0,0,0))
	xbrz_data = image_to_data(xbrz_img)

	scales = xbrz_scales[scale]
	for x in scales:
		xbrz_data = xbrz(xbrz_data, x)
		border *= x
	xbrz_img = data_to_image(xbrz_data)
	# Surprisingly, xbrz does blend with the alpha layer abit. This can be a bigger problem when applying multiple scales.
	# Use alpha threshold on it to get crisp edges.
	if xbrz_thresh >= 0:
		xbrz_img = alpha_threshold(xbrz_img, xbrz_thresh)
	xbrz_img = ImageOps.crop(xbrz_img, border=border)
	xbrz_data = image_to_data(xbrz_img)
	return xbrz_data

# https://stackoverflow.com/questions/8391411/suppress-calls-to-print-python
class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

@cache_data
def png_to_waifu2x(data, method, arch, color):
	import sys
	import os
	import types
	if 'waifu2x_chainer' not in sys.path:
		sys.path.append('waifu2x_chainer')
	import waifu2x
	
	if not hasattr(png_to_waifu2x, 'gpu'):
		png_to_waifu2x.gpu = -1

	cfg = types.SimpleNamespace()
	cfg.scale_ratio = 2.0
	cfg.tta = True
	cfg.tta_level = 8
	cfg.block_size = 128
	cfg.batch_size = 16
	cfg.method = method # scale, noise, scale_noise
	cfg.arch = arch     # VGG7, UpConv7, ResNet10, UpResNet10
	cfg.color = color   # rgb, y
	cfg.gpu = png_to_waifu2x.gpu
	cfg.model_dir = os.path.join('waifu2x_chainer','models',cfg.arch.lower())
	
	models = waifu2x.load_models(cfg)
	
	src = data_to_image(data)
	# Can get out of memory errors if cuda is multiprocessed
	# TODO: Maybe revisit this? Seems to get away with it for abit before crashing and burning
	try:
		with HiddenPrints():
			dst = waifu2x.upscale_image(cfg, src, models['scale'])
	except Exception as e:
		print(e)
		raise Exception('Could not waifu2x upscale, caught error.')

	return image_to_data(dst)

@cache_data
def xbrz(src_data, scale):
	from subprocess import call
	from os.path import join
	from os import remove, close
	from tempfile import mkstemp
	
	fh, tmpfile = mkstemp()
	close(fh)
	save_data(src_data, tmpfile)
	call([join('xbrzscale', 'xbrzscale'), str(scale), tmpfile, tmpfile])
	data = load_data(tmpfile)
	remove(tmpfile)
	return data

# One of two experimental methods attempting to determine a decent alpha layer for the image coming from waifu2x-chainer
# waifu2x-chainer doesn't handle edges against alpha all that well. There is a lot of staircasing and too much mixing with the alpha channel.
# These methods evaluate the alpha channel values and choose a pivot point to make them full transparent or opaque (More like original Doom pictures anyway)
# Too high a pivot is restrictive and results in staircased edges, too low results in additional 'islands' of pixels outside the main sprite
def alpha_threshold_pixelcount(src_data, dst_data):
	def alpha_pivot(alpha, pivot):
		return Image.eval(alpha, lambda px: 255 if px > pivot else 0)
	def count_pixels(image):
		pixels = [0]*256
		pivot_counts = [0]*256
		for a in image.getdata():
			pixels[a] += 1
		for i in range(256):
			for j in range(i,256):
				pivot_counts[i] += pixels[j]
		return pivot_counts
	
	src = data_to_image(src_data)
	dst = data_to_image(dst_data)
	
	src_alpha = src.split()[-1]
	dst_alpha = dst.split()[-1]
	
	# TODO: Use pixel scaler like xBRZ and compare counts to that. Might want slightly more pixels than just doubling.
	src_pixels = count_pixels(src_alpha)
	src_pixels = src_pixels[1] #* 4
	
	pivot_counts = count_pixels(dst_alpha)
	best_pixels = pivot_counts[0]
	best_pivot = 0
	for i in range(1, 256):
		current_pixels = pivot_counts[i]
		if abs(current_pixels - src_pixels) < abs(best_pixels - src_pixels) and current_pixels >= src_pixels:
			best_pivot = i
			best_pixels = current_pixels
	
	dst.putalpha(alpha_pivot(dst_alpha, best_pivot))
	return image_to_data(dst)

def alpha_threshold_islands(src_data, dst_data):
	import numpy as np
	from scipy import ndimage

	def alpha_pivot(alpha, pivot):
			return Image.eval(alpha, lambda px: 255 if px > pivot else 0)
	def count_islands(image):
			return ndimage.label(np.array(image), np.ones((3,3)))[1]

	src = data_to_image(src_data)
	dst = data_to_image(dst_data)

	src_alpha = src.split()[-1]
	dst_alpha = dst.split()[-1]

	src_islands = count_islands(src_alpha)
	best_islands = count_islands(dst_alpha)
	best_pivot = 0
	for i in range(1, 256):
		current_islands = count_islands(alpha_pivot(dst_alpha, i))
		if abs(current_islands - src_islands) < abs(best_islands - src_islands) and current_islands >= src_islands:
			best_pivot = i
			best_islands = current_islands

	dst.putalpha(alpha_pivot(dst_alpha, best_pivot))
	return image_to_data(dst)

def alpha_threshold(dst, pivot):
	def alpha_pivot(alpha, pivot):
			return Image.eval(alpha, lambda px: 255 if px > pivot else 0)

	dst_alpha = dst.split()[-1]

	dst.putalpha(alpha_pivot(dst_alpha, pivot))
	return dst

def has_transparency(data):
	from PIL import ImageStat
	src = data_to_image(data)
	ret = ImageStat.Stat(src).extrema[3] != (255, 255)
	src.close()
	return ret

def image_to_data(image):
	with io.BytesIO() as out_io:
		# 'grAb' is lost here. Shouldn't really matter since this should be used in 'hires', but maybe there are cases where this would be a problem.
		image.save(out_io, format='PNG')
		ret = out_io.getvalue()
		image.close()
		return ret

def data_to_image(data):
	with io.BytesIO(data) as in_io:
		in_io.seek(0)
		image = Image.open(in_io)
		image.load()
		return image

class PictureSanity(Exception):
	pass

# https://doomwiki.org/wiki/Picture_format
# Sanity checks from GZDoom patchtexture.cpp:CheckIfPatch()
# TODO: Pleiades.wad skies hack
class Picture():
	def __init__(self, data):
		data_size = len(data)
		if data_size < 13:
			raise PictureSanity("Failed picture format sanity check!")
		
		data_file = io.BytesIO(data)
		data_file.seek(0)
		width, height, leftoffset, topoffset = struct.unpack('HHhh', data_file.read(8))
		
		if not (height > 0 and height <= 2048 and width > 0 and width <= 2048 and width < data_size / 4):
			raise PictureSanity("Failed picture format sanity check!")
		
		columns = []
		for i in range(width):
			columns.append({
				'offset': struct.unpack('I', data_file.read(4))[0],
				'index': i
			})
			if columns[-1]['offset'] >= data_size:
				raise PictureSanity("Failed picture format sanity check!")
		
		current_top = -1
		for column in columns:
			data_file.seek(column['offset'])
			posts = []
			while True:
				topdelta, = struct.unpack('B', data_file.read(1))
				if topdelta is 255:
					break
				# Detect tall patch
				if len(posts) > 0 and topdelta <= current_top:
					current_top += topdelta
				else:
					current_top = topdelta
				
				length, pad1 = struct.unpack('BB', data_file.read(2))
				data = []
				for i in range(length):
					data.append(struct.unpack('B', data_file.read(1))[0])
				pad2 = struct.unpack('B', data_file.read(1))
				posts.append({
					'topdelta': current_top,
					'length': length,
					'pad1': pad1,
					'data': data,
					'pad2': pad2
				})
			column['posts'] = posts
		
		self.data_file = data_file
		self.height = height
		self.width = width
		self.leftoffset = leftoffset
		self.topoffset = topoffset
		self.columns = columns
	
	def to_rgba(self, palette):
		# Zeros will init as transparent pixels
		rgba = io.BytesIO(b'\0' * self.width * self.height * 4)
		for column in self.columns:
			for post in column['posts']:
				topdelta = post['topdelta']
				for entry in post['data']:
					# TODO: I think all this seeking is hilariously inefficient, should find a way to make this better. Though with caching it hardly matters.
					rgba.seek(topdelta * (self.width * 4) + (column['index'] * 4))
					r, g, b = palette[entry]
					rgba.write(struct.pack('BBBB', r, g, b, 255))
					topdelta += 1
		rgba_bytes = rgba.getvalue()
		rgba.close()
		return rgba_bytes
	
	def to_image(self, palette):
		return Image.frombytes('RGBA', (self.width, self.height), self.to_rgba(palette))

class RawSanity(Exception):
	pass

# https://zdoom.org/wiki/Raw_image
# https://zdoom.org/wiki/Flat
class Raw():
	def __init__(self, data):
		self.size = len(data)
		# Support flats (normal, heretic, hexen, hires2x, hires4x). Then other known raw image dimensions.
		for width, height in [(64, 64), (64, 65), (64, 128), (128, 128), (256, 256), (320, 200), (320, 158), (16, 16), (48, 48), (32, 64)]:
			if width * height == self.size:
				self.width = width
				self.height = height
				break
		# Support AUTOPAGE at any height
		# else executes here if the for loop did not break, see https://stackoverflow.com/questions/9979970/why-does-python-use-else-after-for-and-while-loops
		else:
			if self.size % 320 == 0:
				self.width = 320
				self.height = self.size / 320
			else:
				raise RawSanity('Dimensions of raw image could not be determined!')
		self.data = data
	
	def to_rgba(self, palette):
		# Zeros will init as transparent pixels
		rgba = io.BytesIO(b'\0' * self.width * self.height * 4)
		for entry in self.data:
			r, g, b = palette[entry]
			rgba.write(struct.pack('BBBB', r, g, b, 255))
		rgba_bytes = rgba.getvalue()
		rgba.close()
		return rgba_bytes
	
	def to_image(self, palette):
		return Image.frombytes('RGBA', (self.width, self.height), self.to_rgba(palette))

# Try to detect and handle any ZDoom graphic format
# https://stackoverflow.com/questions/5165317/how-can-i-extend-image-class
class ZImage():
	def __init__(self, data, palette, convert=True):
		self.leftoffset = self.topoffset = None
		if isinstance(data, Image.Image):
			self._img = data
			self.width, self.height = self._img.size
			return
		try:
			try:
				self.width, self.height, self.leftoffset, self.topoffset = png_zmeta(data)
			except:
				pass
			with io.BytesIO(data) as data_io:
				self._img = Image.open(data_io)
				self._img.load()
				self._img = self._img.convert('RGBA')
			self.width, self.height = self._img.size
		except:
			try:
				picture = Picture(data)
				self.leftoffset = picture.leftoffset
				self.topoffset = picture.topoffset
				self.width = picture.width
				self.height = picture.height
				if convert: 
					self._img = picture.to_image(palette)
			except PictureSanity:
				try:
					raw = Raw(data)
					self.width = raw.width
					self.height = raw.height
					if convert:
						self._img = raw.to_image(palette)
				except RawSanity:
					raise Exception("Could not handle image!")

	# Try to act like 'Image' most of the time
	def __getattr__(self, key):
		if key == '_img':
			#  http://nedbatchelder.com/blog/201010/surprising_getattr_recursion.html
			raise AttributeError()
		return getattr(self._img, key)

	def to_png(self):
		if self.leftoffset != None:
			from PIL import PngImagePlugin
			import zlib
		
			def _crc32(data, seed=0):
				return zlib.crc32(data, seed) & 0xffffffff
			
			with io.BytesIO() as png:
				pnginfo = PngImagePlugin.PngInfo()
				# There is a bug in PngImagePlugin, it can't just write arbitrary chunk names, just particular ones in a couple lists.
				# https://pillow.readthedocs.io/en/stable/_modules/PIL/PngImagePlugin.html#PngInfo
				# Look near 'info = im.encoderinfo.get("pnginfo")'
				# So add a 'valid' chunk name. 'iTXt' is nice because it can be added multiple times. Then replace its name in the output.
				grab_data = struct.pack('>ii', self.leftoffset, self.topoffset)
				pnginfo.add(b'iTXt', grab_data)
				# TODO: Support 'alPh'?
				self.save(png, format='PNG', pnginfo=pnginfo)
				png_bytes = png.getvalue()
				png_bytes = png_bytes.replace(
					b'iTXt' + grab_data + struct.pack('>I', _crc32(grab_data, _crc32(b'iTXt'))),
					b'grAb' + grab_data + struct.pack('>I', _crc32(grab_data, _crc32(b'grAb'))), 1)
				return png_bytes
		else:
			with io.BytesIO() as png:
				self.save(png, format='PNG')
				png_bytes = png.getvalue()
				return png_bytes

def png_zmeta(png_data):
	# Skip header
	if png_data[:8] != b'\x89PNG\r\n\x1a\n':
		raise Exception('Not a valid PNG!')
	png_data = png_data[8:]

	leftoffset = None
	topoffset = None
	width = None
	hieght = None
	while png_data:
		length = struct.unpack('>I', png_data[:4])[0]
		png_data = png_data[4:]

		chunk_type = png_data[:4]
		png_data = png_data[4:]
		# Don't bother going past the actual data, just looking for metadata
		if chunk_type == b'IDAT':
			break

		chunk_data = png_data[:length]
		png_data = png_data[length:]

		crc = struct.unpack('>I', png_data[:4])[0]
		png_data = png_data[4:]

		if chunk_type == b'IHDR':
			width, height, bit_depth, color_type, compression_method, filter_method, interlace_method = struct.unpack('>IIBBBBB', chunk_data)
		if chunk_type == b'grAb':
			leftoffset, topoffset = struct.unpack('>ii', chunk_data)
			break

	return width, height, leftoffset, topoffset
