#!/usr/bin/python3
import re

#Tartalmazza-e a kimenet a paraméterben meadott kifejezéseket (reguláris is lehet) (ÉS,VAGY viszonyban)
#Multi: kifejezések elválasztása ';' karakterrel
#használatára a containAnd ill. containOr szolgál
def contain(input, param, ORType):
	param = param.split(';')
	for j in param:
		if re.search(re.sub('\s+','\s*',j), input) == None:
			return ORType
	return not ORType

def containAnd(input, param):
	return contain(input, param, False)

def containOr(input, param):
	return contain(input, param, True)


#Az adott paraméter (mely tartalmazhat reguláris kifejezéseket) illeszkedik-e a kapott bemenetre
def reqexpToInput(input, param):
	param = re.sub('\s+','\s*',param)
	return re.search(param, input)


#A kimenet oszlopnevei között megtalálható-e minden a paraméterven megadott ','-vel elválasztott oszlopnév
def ColumnsEqualParam(input,param):
	rows = input.split('\n')
	firstColumns = rows[0].replace('"','').split(',')
	paramColumns = param.split(',')
	return set(firstColumns) == set(paramColumns)

#A kimenet sorainak száma megegyezik-e a paraméterben kapott számmal
def rowNumEq(input,param):
	return len(input.split('\n')) - 1 == int(param)

#A kimenet sorainak száma >= ? a paraméterben kapott számnál
def rowNumGrEq(input,param):
	return len(input.split('\n')) - 1 >= int(param)

#Adott kimeneti cella(cellák|sorok) tartalma megegyezik-e a paraméterben megadott cella(cellák|sorok)-al
#használat:
#	* sorszám,oszlopszám:érték|||...|||...
#	* sorszám,oszlopszám::egész sor|||...|||...
#	* a ||| az összefűzés, jelentése: minden amit néz ÉS kapcsolatban vizsgálja
def cellData(input,param):
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
			for row in rows:
				if containAnd(row if allColumnMode else row.split(',')[int(cellPos[1])],cellStr):
					return True
		elif cellPos[1] == '*' and cellPos[0] != '*':
			if allColumnMode:
				return containAnd(rows[int(cellPos[0])+1],cellStr)
			else:
				for col in rows[int(cellPos[0])+1].split(','):
					if containAnd(col,cellStr):
						return True
		elif cellPos[1] == '*' and cellPos[0] == '*':
			for row in rows:
				for col in row.split(','):
					if containAnd(row if allColumnMode else col,cellStr):
						return True
		elif containAnd(rows[int(cellPos[0])+1] if allColumnMode else rows[int(cellPos[0])+1].split(',')[int(cellPos[1])],cellStr):
			return True
	return False
