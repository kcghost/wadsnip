import io
import struct
from doom.util import cache_data
import soundfile as sf

# https://github.com/chocolate-doom/chocolate-doom/blob/5329fb5d75971138b20abf940ed63635bd2861e0/src/i_pcsound.c#L44
timer_freq = 1193181
counters = [
	0,
	6818, 6628, 6449, 6279, 6087, 5906, 5736, 5575,
	5423, 5279, 5120, 4971, 4830, 4697, 4554, 4435,
	4307, 4186, 4058, 3950, 3836, 3728, 3615, 3519,
	3418, 3323, 3224, 3131, 3043, 2960, 2875, 2794,
	2711, 2633, 2560, 2485, 2415, 2348, 2281, 2213,
	2153, 2089, 2032, 1975, 1918, 1864, 1810, 1757,
	1709, 1659, 1612, 1565, 1521, 1478, 1435, 1395,
	1355, 1316, 1280, 1242, 1207, 1173, 1140, 1107,
	1075, 1045, 1015,  986,  959,  931,  905,  879,
	 854,  829,  806,  783,  760,  739,  718,  697,
	 677,  658,  640,  621,  604,  586,  570,  553,
	 538,  522,  507,  493,  479,  465,  452,  439,
	 427,  415,  403,  391,  380,  369,  359,  348,
	 339,  329,  319,  310,  302,  293,  285,  276,
	 269,  261,  253,  246,  239,  232,  226,  219,
	 213,  207,  201,  195,  190,  184,  179
]

# TODO: Is there a 'superscale' equivalent for sound?

def lump_to_sound(data, fmt='flac', skip_pc=True):
	# TODO: Support arbitrary formats like wav and ogg to begin with
	try:
		dmx = Dmx(data)
		if skip_pc and dmx.is_pc():
			return None
		if fmt == 'flac':
			data = dmx_to_flac(data)
		elif fmt == 'ogg':
			data = dmx_to_ogg(data)
		else:
			raise Exception('Unsupported format!')
		return data
	except:
		pass

@cache_data
def dmx_to_ogg(data):
	return Dmx(data).to_ogg()

@cache_data
def dmx_to_flac(data):
	return Dmx(data).to_flac()

class Dmx():
	def __init__(self, data):
		with io.BytesIO(data) as data_file:
			data_file.seek(0)
			self.format = struct.unpack('<H', data_file.read(2))[0]
			if self.format == 3:
				# Digital sound
				self.samplerate, self.samples = struct.unpack('<HI', data_file.read(6))
				self.samples -= 32
				self.pad1 = data_file.read(16)
				self.raw = data_file.read(self.samples)
				self.pad2 = data_file.read(16)
			elif self.format == 0:
				# PC speaker sound
				self.samples = struct.unpack('<H', data_file.read(2))[0]
				self.raw = data_file.read(self.samples)
			# TODO: There are 2 more formats that are MIDI sounds? At least according to omgifol? Not sure if they are used by anything.
	
	def is_pc(self):
		return self.format == 0
	
	def to_pcmu8(self):
		if self.format == 3:
			return self.raw, self.samplerate, self.samples
		elif self.format == 0:
			with io.BytesIO(self.raw) as data_file:
				data_file.seek(0)
				# Generate a square wave PCM_U8 for emulating PC speaker sound
				with io.BytesIO() as pc_pcm:
					# Arbitrary high/standard sampling frequency
					samplerate = 44100
					volume = 20
					pc_rate = timer_freq * 2
					pc_state = 128 - volume
					pc_count = 0
					tick_count = 0
					note = 0
					note_ticks = int(pc_rate / 140)
					sample_ticks = int(pc_rate / samplerate)
					sample_count = 0
					# self.samples are 'notes' in this context. each note lasts 1/140th of a second
					total_ticks = int(pc_rate * (1/140 * self.samples))
					# Looping through all the ticks of the pc speaker timer chip as I understand it, then 'sampling' from its output
					# This is hilariously inefficient, but very accurate afaik. I could be wrong though. I often am. Also I am sure there is a better way to do it.
					ticks = 0
					while ticks < total_ticks:
						# Skip ahead to next event, makes this loop a lot faster
						next_note = note_ticks - (ticks % note_ticks) if (ticks % note_ticks) else 0
						next_sample = sample_ticks - (ticks % sample_ticks) if (ticks % sample_ticks) else 0
						if pc_count > 0:
							ticks += min(next_note, next_sample, pc_count)
							tick_count += min(next_note, next_sample, pc_count)
						else:
							ticks += min(next_note, next_sample)
						
						if ticks % note_ticks == 0:
							try:
								pc_count = counters[self.raw[note]]
								note += 1
							except:
								pass

						if pc_count == 0:
							pc_state = 128
							tick_count = 0
						elif tick_count >= pc_count:
							tick_count = 0
							if pc_state > 127:
								pc_state = 128 - volume
							else:
								pc_state = 128 + volume
						else:
							tick_count += 1
						
						if ticks % sample_ticks == 0:
							pc_pcm.write(struct.pack('B',int(pc_state)))
							sample_count += 1
						
						ticks += 1
					# Unmangled waveform, OGG will make it jaggy
					return pc_pcm.getvalue(), samplerate, sample_count
	
	def to_format(self, format):
		raw, samplerate, samples = self.to_pcmu8()
		with io.BytesIO(raw) as data_file:
			data_file.seek(0)
			data, samplerate = sf.read(data_file, channels=1, samplerate=samplerate, frames=samples, subtype='PCM_U8', format='RAW')
			with io.BytesIO() as out_file:
				sf.write(out_file, data, samplerate, format=format)
				return out_file.getvalue()
	
	def to_ogg(self):
		return self.to_format('OGG')
	
	def to_flac(self):
		return self.to_format('FLAC')
