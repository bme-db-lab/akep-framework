from moduls.resultContent import resultContent as rs
from moduls.schemaSpecificAttr import *
from moduls.exceptions import *
import moduls.evaluateFunctions as evaluateFunctions

import copy
import re
import operator

'''
Evaluate Modul
This modul evaluates all //solution element, which contain 
evaluateMode attribute in default case, but you can change element
name in schemaSpeific.py.
These elements will get score attribute by solutionEvaluateAndPut Fn. too.
There are 3 score tree: minus, plus, normal. In solution tag you have to define
the plus and minus type in the tree's root with scoreType attribute by default.
Scores spread up in tree. So if you don't create score attribute on every level
scores inherited from low level (from leaves = solution with evaluateMode).
If you create a solution without evaluateMode it will be a container, where you
can define the children solutions' relationship (or,and,xor) with operator attr.
If you use and relationship between solutions and continer solution does not have
score akep will give subscore.
evaluateMode required value, which reference the function name from evaluateFunctions
'''


class evaluate:
    def __init__(self, channelsGetTastkOutputFn, resultContent, logger):
        """
        Constructor
        channels = channel class instance
        resultContent = resultContent class instance
        logger = loggger instance
        """

        self.getTaskOutputFn = channelsGetTastkOutputFn
        self.resultContent = resultContent
        self.logger = logger
        self.toAnalyse = []
        self.taskAnalyse = []
        self.channelOutputToSolutionId = 0

    def run(self):
        """
        Start the evulation process, results will be store in the specific solution elements
        in resultContent
        """
        score, maxScore = self.__evaluateAll(self.resultContent.resultXMLRoot)
        # result score and max score put the root element
        self.resultContent.resultXMLRoot.set('resultScore', self.__formatScore(score))
        self.resultContent.resultXMLRoot.set('maxScore', self.__formatScore(maxScore))

        if self.resultContent.resultXMLRoot.find('scoreSpecial') is not None:
            self.scoreSpecialEvaluator(self.resultContent.resultXMLRoot.find('scoreSpecial'))
            score = float(self.resultContent.resultXMLRoot.get('resultScore'))
            maxScore = float(self.resultContent.resultXMLRoot.get('maxScore'))

        self.scoreToAnalyse = score if maxScore == 0 else self.__formatScore(score / maxScore * 100)

    def repleaceAllSignFromText(self, text, valueStoreObject, sign='@'):
        for key, value in valueStoreObject.items():
            text = text.replace(sign + key, str(value))
        return text

    def scoreSpecialEvaluator(self, scoreSpecial):
        if scoreSpecial is None:
            return
        try:
            scoreAttrs = {
                'this': scoreSpecial.getparent().get('resultScore'),
                'all': sum(float(resultScore) for resultScore in self.resultContent.resultXMLRoot.xpath(
                    'task/@resultScore'))
            }
            for scoreAttr in scoreSpecial.findall('scoreAttr'):
                attrToSum = '/' + ('@resultScore' if scoreAttr.get('attrName') is None else scoreAttr.get('attrName'))
                scoreAttrs[scoreAttr.get('name')] = sum(
                    float(resultScore) for resultScore in self.resultContent.resultXMLRoot.xpath(
                        scoreAttr.get('xpath') + attrToSum))

            for scoreCondition in scoreSpecial.findall('scoreCondition'):
                scoreCondition.text = self.repleaceAllSignFromText(scoreCondition.text, scoreAttrs)
                if not eval(re.sub('\s+', ' ', scoreCondition.text).strip()):
                    scoreCondition.set('result', 'false')
                    return

            for scoreResult in scoreSpecial.findall('scoreResult'):
                scoreResult.text = self.repleaceAllSignFromText(scoreResult.text, scoreAttrs)
                score = eval(re.sub('\s+', ' ', scoreResult.text).strip())
                addTo = scoreResult.get('addTo')
                if scoreResult.get('type') is not None and addTo is None and scoreSpecial.getparent().tag != 'solution':
                    oldScore = scoreSpecial.getparent().get('resultScore')
                    score = ((-1) * score) if scoreResult.get('type') == 'minus' else score
                    scoreSpecial.getparent().set('resultScore', self.__formatScore(
                        (float(oldScore) + score) if oldScore is not None else score))
                elif addTo is not None:
                    oldScore = scoreSpecial.getparent().get(addTo)
                    scoreSpecial.getparent().set(addTo, self.__formatScore(
                        (float(oldScore) + score) if oldScore is not None else score))
                else:
                    for scoreType in ['resultScore', 'maxScore']:
                        oldScore = scoreSpecial.getparent().get(scoreType)
                        scoreSpecial.getparent().set(scoreType, self.__formatScore(
                            (float(oldScore) + score) if oldScore is not None else score))
        except Exception as err:
            self.logger.exception('scoreSpecialEvaluator error')
            scoreSpecial.set('error', str(err))

    def __evaluateAll(self, taskElement):
        """
        Recursive function to start evaluate recursive function from all task element
        and sum scores
        """
        # if task has solution element
        if self.resultContent.get(element=taskElement, tag=SOLUTION_TAG, direct=True) is not None:
            # three score tree
            normalResult = self.__solutionEvaluateAndPut(taskElement, taskElement)
            bonusResult = self.__solutionEvaluateAndPut(taskElement, taskElement, SCORE_TYPE[0])
            minusResult = self.__solutionEvaluateAndPut(taskElement, taskElement, SCORE_TYPE[1])
            # ... and the result is
            # formal: score, max score (without minus or plus)
            score = normalResult[1] + bonusResult[1] - minusResult[1], normalResult[2]
            self.taskAnalyse.append([rs.getAttrValue(taskElement, 'n'), str(score[0]), str(score[1])])
            return score[0], score[1]

        score = 0
        maxScore = 0
        # if task has task element
        for task in self.resultContent.getAll(element=taskElement, tag=TASKTAG, direct=True):
            for requiredOutput in self.resultContent.getAll(element=task, tag=CH_OUT_TOTASK, direct=True):
                taskOutput = self.getTaskOutputFn(rs.getAttrValue(requiredOutput, SOLUTION_CH_NAME),
                                                  rs.getAttrValue(task, TASK_ELEMENT_ID),
                                                  False if rs.getAttrValue(requiredOutput,
                                                                           SOL_SHOULD_ERROR) is None else True)
                rs.setText(requiredOutput, taskOutput[0] if taskOutput[1] else 'Error: ' + str(taskOutput[0]))
            scoreItem, maxScoreItem = self.__evaluateAll(task)
            scoreItem = self.__dependencyCheck(task, scoreItem=scoreItem)[1]
            rs.setAttr(task, 'resultScore', self.__formatScore(scoreItem))
            rs.setAttr(task, 'maxScore', self.__formatScore(maxScoreItem))

            if task.find('scoreSpecial') is not None:
                self.scoreSpecialEvaluator(task.find('scoreSpecial'))
                scoreItem = float(task.get('resultScore'))
                maxScoreItem = float(task.get('maxScore'))

            score += scoreItem
            maxScore += maxScoreItem

        return score, maxScore

    def __formatScore(self, score, formatText='{0:.2f}'):
        """
        Format score style to two decimal point
        """
        return formatText.format(round(score, 2))

    def __dependencyCheck(self, element, result=None, scoreItem=None):
        dependencies = self.resultContent.getAll(element=element, tag='dependency', direct=True)
        for dependency in dependencies:
            if rs.getAttrValue(dependency, TASK_ELEMENT_ID) is not None:
                depTarget = self.resultContent.get(tag=TASKTAG, attrName=TASK_ELEMENT_ID,
                                                   attrValue=rs.getAttrValue(dependency, TASK_ELEMENT_ID))
            else:
                depTarget = self.resultContent.get(attrName=REFERENCE_TARGET_ID,
                                                   attrValue=rs.getAttrValue(dependency,
                                                                             REFERENCE_ID))

            depScore = 0 if depTarget is None else rs.getAttrValue(depTarget, 'resultScore')
            minScore = rs.getAttrValue(dependency, 'minScore')
            depConditionFail = depScore is None or minScore is not None and float(depScore) < float(
                minScore) or minScore is None and float(depScore) == 0

            if depTarget is None or depConditionFail:
                scoreItem = 0
                result = False
                rs.setAttr(dependency, TO_ELEMENT_ERROR_ATTR, 'reference' if depTarget is None else 'condition')
        return (result, scoreItem)

    def __solutionEvaluateAndPut(self, element, task, scoreType=None, parentOperator=None):
        """
        Evaluate all soluiton tag with evaluateMode attribute
        """
        '''If you would like to write next sentence:
           S1 and (S2 or S3) you have to create a solution container to every bracket with operator attribute and the [and,xor,default=or] value which represent the children solution relationship'''

        # if solution has evaluateMode attr
        evulationMode = rs.getAttrValue(element, EVULATION_MODE_ATTR)
        if evulationMode is not None:
            self.channelOutputToSolutionId += 1
            solID = ((parentOperator + '.') if parentOperator is not None else '') + str(
                element.getparent().index(element))
            requiredSolution = re.sub('\s+', ' ', element.text).strip().lower()
            fromErrorStream = rs.getAttrValue(element, SOL_SHOULD_ERROR)
            # get a tuple: channel output or error text, output is failed to the actual task?
            taskOutput = self.getTaskOutputFn(rs.getAttrValue(element, SOLUTION_CH_NAME),
                                              rs.getAttrValue(task, TASK_ELEMENT_ID),
                                              True if fromErrorStream is not None else False, element)

            taskOutputToChannel = None
            for ch_out in task.xpath(CH_OUT_TOTASK+'[@channelOutputToSolutionId]'):
                if ch_out.text == str(taskOutput[0]):
                    taskOutputToChannel = ch_out
                    break

            if taskOutputToChannel is None:
                element.set('channelOutputToSolutionId', str(self.channelOutputToSolutionId))
                newAttr = {SOLUTION_CH_NAME: rs.getAttrValue(element, SOLUTION_CH_NAME),
                           'channelOutputToSolutionId': str(self.channelOutputToSolutionId)}

                if fromErrorStream is not None:
                    newAttr[SOL_SHOULD_ERROR] = ''

                taskOutputElement = rs.createElement(CH_OUT_TOTASK, newAttr)
                rs.setText(taskOutputElement, taskOutput[0] if taskOutput[1] else 'Error: ' + str(taskOutput[0]))
                rs.appendTo(taskOutputElement, task)
            else:
                element.set('channelOutputToSolutionId', taskOutputToChannel.get('channelOutputToSolutionId'))

            score = 0 if rs.getAttrValue(element, SCORE_ATTR) is None else float(rs.getAttrValue(element, SCORE_ATTR))
            try:
                # if channel output not failed to actual task or we would like to evaluate the error
                if taskOutput[1]:
                    result = getattr(evaluateFunctions, evulationMode)(str(taskOutput[0]).strip().lower(),
                                                                       requiredSolution,
                                                                       rs.getAttrValue(element, SOL_OTHER_OPTION))
                    # negate the result if solution has Negation attr
                    result = not result if rs.getAttrValue(element, SOL_NEGATION) is not None else result
                    self.toAnalyse.append(
                        [rs.getAttrValue(task, TASK_ELEMENT_ID), solID, evulationMode, str(score if result else 0), ''])
                    return (result, (score if result else 0), score)
            except:
                self.logger.exception(
                    'Evaluate error in channel {} with {} taskID'.format(rs.getAttrValue(element, SOLUTION_CH_NAME),
                                                                         rs.getAttrValue(task, TASK_ELEMENT_ID)))
                rs.setAttr(element, TO_ELEMENT_ERROR_ATTR, 'evaluateError')
                self.toAnalyse.append(
                    [rs.getAttrValue(task, TASK_ELEMENT_ID), solID, evulationMode, '0', 'evaluate error'])
                return (False, 0, score)

            self.toAnalyse.append([rs.getAttrValue(task, TASK_ELEMENT_ID), solID, evulationMode, '0', 'channel error'])
            # set error to actual solution element
            rs.setAttr(element, TO_ELEMENT_ERROR_ATTR, 'channelError')
            # return format: result [True,False], score to the result, max score
            return (False, 0, score)

        # This section will run if element does not have evaluateMode attr
        results = []
        score = 0
        maxScore = 0
        # if operator is and AKEP give subscore and sum the solutions scores in the container
        # else max score will return calculated
        operatorType = 'or' if rs.getAttrValue(element, SOL_OPERATOR) is None else rs.getAttrValue(element,
                                                                                                   SOL_OPERATOR)
        scoreFunc = sum if operatorType == 'and' else max
        for childSolution in self.resultContent.getAll(element=element, tag=SOLUTION_TAG, direct=True):
            # if element has children solition elements
            if element.tag != TASKTAG or rs.getAttrValue(childSolution, SOL_SCORE_TYPE) == scoreType:
                result, scoreItem, maxScoreItem = self.__solutionEvaluateAndPut(childSolution, task, parentOperator=(
                    parentOperator + '.' + operatorType) if parentOperator is not None else operatorType)

                result, scoreItem = self.__dependencyCheck(childSolution, result, scoreItem)

                score = scoreFunc([score, scoreItem])  # if result else 0
                maxScore = scoreFunc([maxScore, maxScoreItem])
                rs.setAttr(childSolution, 'result', 'true' if result else 'false')
                rs.setAttr(childSolution, 'resultScore', self.__formatScore(scoreItem))
                if childSolution.find('scoreSpecial') is not None:
                    self.scoreSpecialEvaluator(childSolution.find('scoreSpecial'))
                results.append(result)
        # default solution has or relationship with neighbour solutions
        # final result is calculated with __multiOperations
        finalResult = self.__multiOperations(operatorType, copy.copy(results))
        finalResult = not finalResult if rs.getAttrValue(element, SOL_NEGATION) is not None else finalResult

        if finalResult:
            score = float(rs.getAttrValue(element, SCORE_ATTR)) if rs.getAttrValue(element,
                                                                                   SCORE_ATTR) is not None else score
        else:
            score = 0 if rs.getAttrValue(element, SCORE_ATTR) is not None else score

        # if container tag has score and finalResult True it will be result else the children function score return
        return (finalResult, score,
                float(rs.getAttrValue(element, SCORE_ATTR)) if rs.getAttrValue(element, SCORE_ATTR) else maxScore)

    def __multiOperations(self, opType, operands):
        """
        Recursive function to process the sentence
        """
        if len(operands) < 2:
            # only two operand is allow
            return False
        if len(operands) == 2:
            if opType == "or":
                return operands[0] or operands[1]
            elif opType == "and":
                return operands[0] and operands[1]
            elif opType == "xor":
                return operator.xor(operands[0], operands[1])
            else:
                raise AKEPException(ERROR['GENERAL']['NOT_SUPPORTER_SENT'] + opType)
        leftOperand = operands.pop(0)
        rightOperand = self.__multiOperations(opType, operands)
        return self.__multiOperations(opType, [leftOperand, rightOperand])
