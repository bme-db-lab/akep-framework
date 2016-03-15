#!/usr/bin/python3
#
# Channel is a source of data for the evaluator, line source code, or output.

from enum import Enum

'''Available channel types'''
class ChannelType(Enum):
	sourceCode = 1
	output = 2
