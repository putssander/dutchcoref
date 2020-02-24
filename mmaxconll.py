"""Convert SoNaR coreference annotations to CoNLL 2012 format.

Usage: mmaxconll.py <inputdir> [outputfile]

inputdir should have directories called Basedata and Markables.
output is written on stdout if no output is specified."""
import os
import re
import sys
import glob
import getopt
from lxml import etree


def getspan(markable, idxmap, words):
	"""Convert an MMAX span into integer indices."""
	start = end = span = markable.attrib['span']
	if ',' in span:
		head = markable.get('head', '').lower()
		for component in span.split(','):
			start = end = component
			if '..' in component:
				start, end = component.split('..')
			for n in range(idxmap[start], idxmap[end] + 1):
				if words[n].text.lower() == head:
					return idxmap[start], idxmap[end]
		# didn't find head, return last component as default
		return idxmap[start], idxmap[end]
	if '..' in markable.attrib['span']:
		start, end = markable.attrib['span'].split('..')
	return idxmap[start], idxmap[end]


def getmarkables(words, nplevel, idxmap):
	"""Add start and end tags of markables to the respective tokens."""
	seen = set()  # don't add same span twice
	inspan = set()  # track which token ids are in spans
	for markable in nplevel:
		try:
			start, end = getspan(markable, idxmap, words)
		except KeyError:  # ignore spans referring to non-existing tokens
			continue
		if (start, end) in seen:
			continue
		seen.add((start, end))
		inspan.update(range(start, end))  # NB: do not include end!
		# TODO: filter for type of links
		if 'ref' in markable.attrib and markable.get('ref') != 'empty':
			mid = markable.attrib['ref']
		elif 'id' in markable.attrib:
			mid = markable.attrib['id']
		else:
			raise ValueError
		if ';' in mid:  # ignore all but first reference
			mid = mid[:mid.index(';')]
		if not re.match(r'markable_[0-9]+$', mid):
			raise ValueError
		mid = mid.split('_')[1]
		cur = words[start].get('coref', '')
		if start == end:
			coref = ('%s|(%s)' % (cur, mid)) if cur else ('(%s)' % mid)
			words[start].set('coref', coref)
		else:
			coref = ('%s|(%s' % (cur, mid)) if cur else ('(%s' % mid)
			words[start].set('coref', coref)
			cur = words[end].get('coref', '')
			coref = ('%s|%s)' % (cur, mid)) if cur else ('%s)' % mid)
			words[end].set('coref', coref)
	return inspan


def getsents(words, sentence, idxmap):
	"""Extract indices of sentence breaks."""
	# The SoNaR sentence annotations are a mess:
	# duplicate spans, overlapping spans, etc.
	# The approach here is to output all tokens in order, and insert
	# a sentence break if it is annotated (i.e., ignore sentence starts,
	# because it could lead to missing/repeated tokens).
	sentends = set()
	if sentence is None:  # Corea
		for n, word in enumerate(words[1:], 1):
			if word.get('pos') == '0' or word.get('alppos') == '0':
				sentends.add(n - 1)
	else:  # SoNaR
		for markable in sentence:
			try:
				sentends.add(getspan(markable, idxmap, words)[1])
			except KeyError:  # ignore spans referring to non-existing tokens
				pass
	return sentends


def writeconll(words, sentends, doc, inspan, out):
	"""Write tokens and coreference information in CoNLL format."""
	n = 0
	print('#begin document (%s); part 000' % doc, file=out)
	for m, word in enumerate(words):
		print(doc, n, word.text, word.get('coref', '-'), sep='\t', file=out)
		n += 1
		if m in sentends:
			# ignore sent break if any span still open
			if m not in inspan:
				print(file=out)
				n = 0
	print('#end document', file=out)


def conv(fname, inputdir, out):
	"""Convert a set of files for a single MMAX document to CoNLL."""
	words = etree.parse(fname).getroot()
	doc = os.path.basename(fname).replace('_words.xml', '')
	if os.path.exists('%s/Markables/%s_np_level.xml' % (inputdir, doc)):
		nplevel = etree.parse('%s/Markables/%s_np_level.xml'
				% (inputdir, doc)).getroot()
	elif os.path.exists('%s/Markables/%s_coref_level.xml' % (inputdir, doc)):
		nplevel = etree.parse('%s/Markables/%s_coref_level.xml'
				% (inputdir, doc)).getroot()
	if os.path.exists('%s/Markables/%s_sentence_level.xml' % (inputdir, doc)):
		sentence = etree.parse('%s/Markables/%s_sentence_level.xml'
				% (inputdir, doc)).getroot()
	else:
		sentence = None
	# word IDs may be missing or contain decimals;
	# this maps ID labels to integer indices.
	idxmap = {word.attrib['id']: n
			for n, word in enumerate(words)}
	inspan = getmarkables(words, nplevel, idxmap)
	sentends = getsents(words, sentence, idxmap)
	writeconll(words, sentends, doc, inspan, out)


def main():
	"""CLI."""
	try:
		_opts, args = getopt.gnu_getopt(sys.argv[1:], '', [])
	except getopt.GetoptError as err:
		print(err, __doc__, sep='\n')
		return
	if not args or len(args) > 2:
		print(err, __doc__, sep='\n')
		return
	inputdir = args[0]
	out = None if len(args) == 1 else open(args[1], 'w', encoding='utf8')
	pattern = '%s/Basedata/*.xml' % inputdir
	fnames = sorted(glob.glob(pattern))
	if not fnames:
		print('no files found matching: %s' % pattern)
		return
	try:
		for fname in fnames:
			conv(fname, inputdir, out)
	finally:
		if out:
			out.close()


if __name__ == '__main__':
	main()