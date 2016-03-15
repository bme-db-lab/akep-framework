#!/usr/bin/python3
'''Simple helper functions for handling xml.etree.ElementTree nodes.'''

import xml.etree.ElementTree as ET

def ETappendChildTruncating(node, childName, textContent, cnt=0):
	'''Append a child node to the ElementTree node passed in, truncating after cnt characters.

	Truncating occures only if cnt is positive. Zero means no truncating. If truncated, add warning attribute. Return the new child node itself.
	'''
	ChET = ET.SubElement(node, childName)
	if textContent is not None and cnt > 0 and len(textContent) > cnt:
		ChET.text= textContent[0:cnt-1] + ' !WARNING TOO LONG!'
		# add attributes to indicate warning
		ETaddWarningToNode(ChET, 'Too long: ' + str( len(textContent) ) + 'chars. Truncated after ' + str(cnt) + ' characters.')
	elif textContent is not None and cnt >= 0:
		ChET.text = textContent
	else:
		# textContent is None or cnt < 0, which is unspecified
		ChET.text = None

	return ChET

def ETaddWarningToNode(node, warningText, warningName=None):
	'''Add a textual warning (warningText) to the given node's warning attribute.

	If provided, set the attribute given in warningAttr to true enabling programmatic recognition.
	'''
	previousWarning=node.get('warning')
	if previousWarning is None:
		node.set('warning', warningText)
	else:
		node.set('warning', previousWarning + '; ' + warningText)

	if warningName is not None:
		node.set(warningName, 'true')
