#!/usr/bin/python3
import re

#Visszad egy dictionary-t egy olyan string-ből, melyben ;-vel elválasztott key:value szerepel
def getDictFromArgs(Args):
	resDict = {}
	if Args is None:
		return resDict
	items = Args.split(';')
	for item in filter(None, items): # üres elemek kihagyása
		keyvalue = item.split(':')
		if keyvalue[0] not in resDict:
			resDict[keyvalue[0]] = []
		resDict[keyvalue[0]].append(keyvalue[1])
	return resDict

#Tartalmazza-e a kimenet a paraméterben meadott kifejezéseket (reguláris is lehet) (ÉS,VAGY viszonyban)
#Multi: kifejezések elválasztása ';' karakterrel
#használatára a containAnd ill. containOr szolgál
def contain(input, param, ORType, args):
	f = any if ORType else all
	return f(regexpToInput(input, j, args) for j in param.split(';'))

def containAnd(input, param, args):
	return contain(input, param, False,args)

def containOr(input, param, args):
	return contain(input, param, True, args)


#Az adott paraméter (mely tartalmazhat reguláris kifejezéseket) illeszkedik-e a kapott bemenetre
def regexpToInput(input, param, args):
	param = re.sub('\s+','\s*',param)
	dictArgs = getDictFromArgs(args)
	if 'skipchar' in dictArgs:
		for skipchar in dictArgs['skipchar']:
			input = input.replace(skipchar,'')
	return re.search(param, input, re.DOTALL)


#A kimenet oszlopnevei között megtalálható-e minden a paraméterven megadott ','-vel elválasztott oszlopnév
def ColumnsEqualParam(input,param, args):
	rows = input.split('\n')
	firstColumns = rows[0].replace('"','').split(',')
	paramColumns = param.split(',')
	find = 0;
	for paramColumn in paramColumns:
		for col in firstColumns:
			if regexpToInput(col,paramColumn,args):
				find += 1
				break

	#return set(firstColumns) == set(paramColumns)
	return find == len(paramColumns)

#A kimenet sorainak száma megegyezik-e a paraméterben kapott számmal
def rowNumEq(input,param, args):
	return len(input.split('\n')) - 1 == int(param)

#A kimenet sorainak száma >= ? a paraméterben kapott számnál
def rowNumGrEq(input,param, args):
	return len(input.split('\n')) - 1 >= int(param)

#A kimenet sorainak száma <= ? a paraméterben kapott számnál
def rowNumLtEq(input,param, args):
	return len(input.split('\n')) - 1 <= int(param)

#Adott kimeneti cella(cellák|sorok) tartalma megegyezik-e a paraméterben megadott cella(cellák|sorok)-al
#használat:
#	* sorszám,oszlopszám:érték|||...|||...
#	* sorszám,oszlopszám::egész sor|||...|||...
#	* a ||| az összefűzés, jelentése: minden amit néz ÉS kapcsolatban vizsgálja
def cellData(input,param, args):
	rows = input.replace('"','').split('\n')
	for cell in param.split('|||'):
		cellPos = cell.split(':')[0].split(',')
		allColumnMode = False
		if len(cell.split(':')) == 3:
			cellStr = cell.split(':')[2]
			allColumnMode = True
		else:
			cellStr = cell.split(':')[1]

		if cellPos[0] == '*' and cellPos[1] != '*':
			ItContain=False
			for row in rows:
				if not allColumnMode and len(row.split(',')) <= int(cellPos[1]):
					return False #no enough column
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
				return False #no enough row
			if allColumnMode:
				if not containAnd(rows[int(cellPos[0])+1],cellStr, args):
					return False
			else:
				if len(rows[int(cellPos[0])+1].split(',')) <= int(cellPos[1]):
					return False #no enough column
				if not containAnd(rows[int(cellPos[0])+1].split(',')[int(cellPos[1])],cellStr, args):
					return False
	return True
