import io
import struct

# TODO: Support midi, as well as any format GZDoom can support for music
class Mus():
	def __init__(self, data):
		with io.BytesIO(data) as data_file:
			data_file.seek(0,2)
			total_size = data_file.tell()
			data_file.seek(0)

			self.sig = struct.unpack('<4s', data_file.read(4))[0]
			if self.sig != b'MUS\x1A':
				raise Exception("Sanity check failure for MUS music!")
			# TODO: Actually support MUS :)
