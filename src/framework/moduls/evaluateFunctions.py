#!/usr/bin/python3
import re
import collections

CSVDelimiter = '-#-'

def getDictFromArgs(Args):
    resDict = collections.defaultdict(list)
    if Args is None:
        return resDict
    items = Args.split(';')
    for item in filter(None, items):  # üres elemek kihagyása
        key, value = item.split(':')
        resDict[key].append(value)
    return resDict


def contain(input, param, ORType, args):
    if param.endswith(';'):
        param = param[:-1]
    f = any if ORType else all
    return f(regexpToInput(input, j, args) for j in param.split(';'))


def containAnd(input, param, args):
    """
    Does input contain all items from param?
    Format: <regular pattern 1>;…;<regular pattern N>
    """
    return contain(input, param, False, args)


def containOr(input, param, args):
    """
    Format: <regular pattern 1>;…;<regular pattern N>
    """
    return contain(input, param, True, args)


def regexpToInput(input, param, args):
    """
    Format: <regular pattern>
    """
    if input == '' and param == '':
        return True
    if param == '':
        return False
    param = re.sub('\s+', '\s*', param)
    dictArgs = getDictFromArgs(args)
    for skipchar in dictArgs['skipchar']:
        input = input.replace(skipchar, '')
    return re.search(param, input, re.DOTALL)


def ColumnsEqualParam(input, param, args):
    """
    Does input has the same attributes in first row than items from param?
    Format: <regular pattern 1>,…,<regular pattern N>
    """
    delimiter = CSVDelimiter if CSVDelimiter in input else ','
    rows = input.split('\n')
    firstColumns = rows[0].replace('"', '').split(delimiter)
    paramColumns = param.split(delimiter)
    find = 0
    for paramColumn in paramColumns:
        for col in firstColumns:
            if regexpToInput(col, paramColumn, args):
                find += 1
                break

    return find == len(paramColumns)


def rowNumEq(input, param, args):
    """
    Format: <Natural number>
    """
    return len(input.split('\n')) - 1 == int(param)


def rowNumGrEq(input, param, args):
    """
    Format: <Natural number>
    """
    return len(input.split('\n')) - 1 >= int(param)


def rowNumLtEq(input, param, args):
    """
    Format: <Natural number>
    """
    return len(input.split('\n')) - 1 <= int(param)


def cellData(input, param, args):
    '''
    Does tranformed table (from input) contain a cell or a row based on param?
    ----
    * (star) symbolum marks in this context that it is a undefined row/column index
    cell expression = ([0-9]+|*),([0-9]+|*):<cell regular pattern>
    Format (1): <cell expression 1>|||…|||<cell expression N>
    Format (2): ([0-9]+|*),*::<whole row regular pattern 1>|||…|||([0-9]+|*),*::<whole row regular pattern N>
    '''
    delimiter = CSVDelimiter if CSVDelimiter in input else ','
    rows = input.replace('"', '').split('\n')
    for cell in param.split('|||'):
        cellPos = cell.split(':')[0].split(',')
        allColumnMode = False
        if len(cell.split('::')) == 2:
            cellStr = cell.split('::')[1]
            allColumnMode = True
        else:
            cellStr = cell.split(':')[1]

        if cellPos[0] == '*' and cellPos[1] != '*':
            ItContain = False
            for row in rows:
                if not allColumnMode and len(row.split(delimiter)) <= int(cellPos[1]):
                    return False
                if containAnd(row if allColumnMode else row.split(delimiter)[int(cellPos[1])], cellStr, args):
                    ItContain = True
                    break
            if not ItContain:
                return False
        elif cellPos[1] == '*' and cellPos[0] != '*':
            if len(rows) <= int(cellPos[0]) + 1:
                return False  # no enough row
            if allColumnMode:
                if not containAnd(rows[int(cellPos[0]) + 1], cellStr, args):
                    return False
            else:
                ItContain = False
                for col in rows[int(cellPos[0]) + 1].split(delimiter):
                    if containAnd(col, cellStr, args):
                        ItContain = True
                        break
                if not ItContain:
                    return False
        elif cellPos[1] == '*' and cellPos[0] == '*':
            ItContain = False
            for row in rows:
                for col in row.split(delimiter):
                    if containAnd(row if allColumnMode else col, cellStr, args):
                        ItContain = True
                        break
                if ItContain:
                    break
            if not ItContain:
                return False
        else:
            if len(rows) <= int(cellPos[0]) + 1:
                return False
            if allColumnMode:
                if not containAnd(rows[int(cellPos[0]) + 1], cellStr, args):
                    return False
            else:
                if len(rows[int(cellPos[0]) + 1].split(delimiter)) <= int(cellPos[1]):
                    return False
                if not containAnd(rows[int(cellPos[0]) + 1].split(delimiter)[int(cellPos[1])], cellStr, args):
                    return False
    return True
