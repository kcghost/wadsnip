#!/usr/bin/env python3
import re
from doom.util import load_data

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


test = load_data('out/square-ep2-pk3-2.1_modernized/textures.base')
text = test.decode('utf-8')
text = comment_remover(text)
text = re.sub(re.compile(r'\s*([{}])\s*', re.DOTALL | re.MULTILINE), r'\1', text)
text = re.sub(re.compile(r'\s*(Patch[^{}\n\r]*)'), r'\1 {}', text)
text = re.sub(re.compile(r'\s*([{}])\s*', re.DOTALL | re.MULTILINE), r'\1', text)
print(text)
