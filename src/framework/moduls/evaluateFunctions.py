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


def emptyTransform(referenceCh, args, inputCh, logger):
    return True, re.escape(re.sub('\s+', ' ', referenceCh)).replace('\\ ', ' ')


def rowNumTransform(referenceCh, args, inputCh, logger):
    return True, len(referenceCh.split('\n')) - 1


def ColumnsEqualParamTransformFromTable(referenceCh, args, inputCh, logger):
    rows = referenceCh.split('\n')
    return True, rows[0].replace('"', '')


def cellDataTransform(referenceCh, args, inputCh, logger):
    params = getDictFromArgs(args)
    transformMode = params['checkType'][0] if len(params['checkType']) == 1 else None
    # columnIndex = params['columnIndex'][0] if len(options['columnIndex']) == 1 else None
    rows = referenceCh.replace('"', '').split('\n')
    if len(rows) == 0:
        return True, 'No required input'

    if transformMode in ['totally', 'notOrdered', 'subsetTotally', 'notOrderedSubset']:
        if transformMode in ['totally', 'notOrdered'] and len(rows) != len(inputCh.split('\n')):
            return False, 'Not equal number of rows'
        result = []
        i = 0
        del rows[0]
        for row in rows:
            res = (str(i) if transformMode in ['totally', 'subsetTotally'] else '*') + ',*::' + row
            result.append(res)
            i += 1
            # logger.debug(res)
        return True, '|||'.join(result)
    return False, 'Not valid transform mode: {}'.format(transformMode)


def makeEvaluateWithReference(evaluateFnName, inputCh, referenceCh, args, logger):
    evaluateFn = evaluateFns.get(evaluateFnName, None)
    if evaluateFn:
        result, requiredString = evaluateFnsTransform[evaluateFnName](referenceCh, args, inputCh, logger)
        if result:
            return evaluateFn(inputCh, requiredString, args, evaluateFnName == 'cellData', logger), requiredString
        return None, requiredString
    return None, 'There is not exist transform function to {} evaluate function'.format(evaluateFnName)


def contain(input, param, ORType, args, fromTransform=False, logger=None):
    if param.endswith(';'):
        param = param[:-1]
    f = any if ORType else all
    return f(regexpToInput(input, j, args, fromTransform, logger) for j in param.split(';'))


def containAnd(input, param, args, fromTransform=False, logger=None):
    """
    Does input contain all items from param?
    Format: <regular pattern 1>;…;<regular pattern N>
    """
    return contain(input, param, False, args, fromTransform, logger)


def containOr(input, param, args, fromTransform=False, logger=None):
    """
    Format: <regular pattern 1>;…;<regular pattern N>
    """
    return contain(input, param, True, args, fromTransform, logger)


def regexpToInput(input, param, args, fromTransform=False, logger=None):
    """
    Format: <regular pattern>
    """
    if input == '' and param == '':
        return True
    if param == '':
        return False
    param = re.sub('\s+', '\s*', param) if fromTransform is False else param
    if logger is not None:
        logger.debug(input)
        logger.debug(param)
        logger.debug(input == param)
    dictArgs = getDictFromArgs(args)
    for skipchar in dictArgs['skipchar']:
        input = input.replace(skipchar, '')
    return re.search(param, input, re.DOTALL) if fromTransform is False else input == param


def ColumnsEqualParam(input, param, args, fromTransform=False, logger=None):
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
            if regexpToInput(col, paramColumn, args, fromTransform, logger):
                find += 1
                break

    return find == len(paramColumns)


def rowNumEq(input, param, args, fromTransform=False, logger=None):
    """
    Format: <Natural number>
    """
    return len(input.split('\n')) - 1 == int(param)


def rowNumGrEq(input, param, args, fromTransform=False, logger=None):
    """
    Format: <Natural number>
    """
    return len(input.split('\n')) - 1 >= int(param)


def rowNumLtEq(input, param, args, fromTransform=False, logger=None):
    """
    Format: <Natural number>
    """
    return len(input.split('\n')) - 1 <= int(param)


def cellData(input, param, args, fromTransform=False, logger=None):
    '''
    Does tranformed table (from input) contain a cell or a row based on param?
    ----
    * (star) symbolum marks in this context that it is a undefined row/column index
    cell expression = ([0-9]+|*),([0-9]+|*):<cell regular pattern>
    Format (1): <cell expression 1>|||…|||<cell expression N>
    Format (2): ([0-9]+|*),*::<whole row regular pattern 1>|||…|||([0-9]+|*),*::<whole row regular pattern N>
    '''

    if param is True or param is False:
        return input

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
                if containAnd(row if allColumnMode else row.split(delimiter)[int(cellPos[1])], cellStr, args,
                              fromTransform, logger):
                    ItContain = True
                    break
            if not ItContain:
                return False
        elif cellPos[1] == '*' and cellPos[0] != '*':
            if len(rows) <= int(cellPos[0]) + 1:
                return False  # no enough row
            if allColumnMode:
                if not containAnd(rows[int(cellPos[0]) + 1], cellStr, args, fromTransform, logger):
                    return False
            else:
                ItContain = False
                for col in rows[int(cellPos[0]) + 1].split(delimiter):
                    if containAnd(col, cellStr, args, fromTransform, logger):
                        ItContain = True
                        break
                if not ItContain:
                    return False
        elif cellPos[1] == '*' and cellPos[0] == '*':
            ItContain = False
            for row in rows:
                for col in row.split(delimiter):
                    if containAnd(row if allColumnMode else col, cellStr, args, fromTransform, logger):
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
                if not containAnd(rows[int(cellPos[0]) + 1], cellStr, args, fromTransform, logger):
                    return False
            else:
                if len(rows[int(cellPos[0]) + 1].split(delimiter)) <= int(cellPos[1]):
                    return False
                if not containAnd(rows[int(cellPos[0]) + 1].split(delimiter)[int(cellPos[1])], cellStr, args,
                                  fromTransform, logger):
                    return False
    return True


evaluateFns = {
    'containAnd': containAnd,
    'containOr': containOr,
    'regexpToInput': regexpToInput,
    'ColumnsEqualParam': ColumnsEqualParam,
    'rowNumEq': rowNumEq,
    'rowNumGrEq': rowNumGrEq,
    'rowNumLtEq': rowNumLtEq,
    'cellData': cellData
}
evaluateFnsTransform = {
    'cellData': cellDataTransform,
    'containOr': emptyTransform,
    'containAnd': emptyTransform,
    'regexpToInput': emptyTransform,
    'ColumnsEqualParam': ColumnsEqualParamTransformFromTable,
    'rowNumEq': rowNumTransform,
    'rowNumGrEq': rowNumTransform,
    'rowNumLtEq': rowNumTransform,
}
