#!/usr/bin/python3
import re
import collections

def getDictFromArgs(Args):
	resDict = collections.defaultdict(list)
	if Args is None:
		return resDict
	items = Args.split(';')
	for item in filter(None, items): # üres elemek kihagyása
		key, value = item.split(':')
		resDict[key].append(value)
	return resDict

def contain(input, param, ORType, args):
	if param.endswith(';'):
		param = param[:-1]
	f = any if ORType else all
	return f(regexpToInput(input, j, args) for j in param.split(';'))

def containAnd(input, param, args):
	return contain(input, param, False,args)

def containOr(input, param, args):
	return contain(input, param, True, args)

def regexpToInput(input, param, args):
	input,res = fromLog(input, args)
	if input == '' and param == '':
		return True
	if param == '':
		return False
	param = re.sub('\s+','\s*',param)
	dictArgs = getDictFromArgs(args)
	for skipchar in dictArgs['skipchar']:
		input = input.replace(skipchar,'')
	return re.search(param, input, re.DOTALL)

def fromLog(input,args):
	if 'fromLog' in getDictFromArgs(args):
		logString = re.match('----log----(.*)----log----',input,flags=re.DOTALL).group(1) or ''
		return logString.strip(),True
	return re.sub('----log----.*----log----','',input,flags=re.DOTALL).strip(),False

def ColumnsEqualParam(input,param, args):
	input,res = fromLog(input, args)
	rows = input.split('\n')
	firstColumns = rows[0].replace('"','').split(',')
	paramColumns = param.split(',')
	find = 0;
	for paramColumn in paramColumns:
		for col in firstColumns:
			if regexpToInput(col,paramColumn,args):
				find += 1
				break

	return find == len(paramColumns)

def rowNumEq(input,param, args):
	input,res = fromLog(input, args)
	rowp = 1 if not res else 0
	return len(input.split('\n')) - rowp == int(param)

def rowNumGrEq(input,param, args):
	input,res = fromLog(input, args)
	rowp = 1 if not res else 0
	return len(input.split('\n')) - rowp >= int(param)

def rowNumLtEq(input,param, args):
	input,res = fromLog(input, args)
	rowp = 1 if not res else 0
	return len(input.split('\n')) - rowp <= int(param)

def cellData(input,param, args):
	input,res = fromLog(input, args)
	if res:
		args = re.sub('fromLog.*;?','',args)

	rows = input.replace('"','').split('\n')
	for cell in param.split('|||'):
		cellPos = cell.split(':')[0].split(',')
		allColumnMode = False
		if len(cell.split('::')) == 2:
			cellStr = cell.split('::')[1]
			allColumnMode = True
		else:
			cellStr = cell.split(':')[1]

		if cellPos[0] == '*' and cellPos[1] != '*':
			ItContain=False
			for row in rows:
				if not allColumnMode and len(row.split(',')) <= int(cellPos[1]):
					return False
				if containAnd(row if allColumnMode else row.split(',')[int(cellPos[1])],cellStr, args):
					ItContain = True
					break
			if not ItContain:
				return False
		elif cellPos[1] == '*' and cellPos[0] != '*':
			if len(rows) <= int(cellPos[0])+1:
				return False #no enough row
			if allColumnMode:
				if not containAnd(rows[int(cellPos[0])+1],cellStr,args):
					return False
			else:
				ItContain=False
				for col in rows[int(cellPos[0])+1].split(','):
					if containAnd(col,cellStr,args):
						ItContain = True
						break
				if not ItContain:
					return False
		elif cellPos[1] == '*' and cellPos[0] == '*':
			ItContain=False
			for row in rows:
				for col in row.split(','):
					if containAnd(row if allColumnMode else col,cellStr, args):
						ItContain=True
						break
				if ItContain:
					break
			if not ItContain:
				return False
		else:
			if len(rows) <= int(cellPos[0])+1:
				return False
			if allColumnMode:
				if not containAnd(rows[int(cellPos[0])+1],cellStr, args):
					return False
			else:
				if len(rows[int(cellPos[0])+1].split(',')) <= int(cellPos[1]):
					return False
				if not containAnd(rows[int(cellPos[0])+1].split(',')[int(cellPos[1])],cellStr, args):
					return False
	return True