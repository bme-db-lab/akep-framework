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

    def __init__(self,channels,resultContent, logger):
        '''Constructor
        channels = channel class instance
        resultContent = resultContent class instance
        logger = loggger instance'''

        self.channels = channels
        self.resultContent = resultContent
        self.logger = logger

    def run(self):
        '''
        Start the evulation process, results will be store in the specific solution elements
        in resultContent'''

        score,maxScore = self.evaluateAll(self.resultContent.resultXMLRoot)
        # result score and max score put the root element
        self.resultContent.resultXMLRoot.set('resultScore',self.formatScore(score))
        self.resultContent.resultXMLRoot.set('maxScore',self.formatScore(maxScore))  

    def evaluateAll(self,taskElement):
        '''
        Recursive function to start evaluate recursive function from all task element
        and sum scores'''
        # if task has solution element
        if self.resultContent.get(element = taskElement, tag = SOLUTION_TAG, direct=True) is not None:
            # three score tree
            normalResult = self.solutionEvaluateAndPut(taskElement,taskElement)
            bonusResult = self.solutionEvaluateAndPut(taskElement,taskElement,SCORE_TYPE[0])
            minusResult = self.solutionEvaluateAndPut(taskElement,taskElement,SCORE_TYPE[1])
            # ... and the result is
            # formal: score, max score (without minus or plus)
            return normalResult[1] + bonusResult[1] - minusResult[1],normalResult[2]
        
        score = 0
        maxScore = 0
        # if task has task element
        for task in self.resultContent.getAll(element = taskElement, tag = TASKTAG, direct = True):
            scoreItem,maxScoreItem = self.evaluateAll(task)
            score += scoreItem
            maxScore += maxScoreItem
            rs.setAttr(task,'resultScore',self.formatScore(scoreItem))
            rs.setAttr(task,'maxScore',self.formatScore(maxScoreItem))
                    
        return score,maxScore

    def formatScore(self,score,formatText='{0:.2f}'):
        '''Format score style to two decimal point'''
        return formatText.format(round(score,2))
                
    def solutionEvaluateAndPut(self,element,task,scoreType=None):
        '''Evaluate all soluiton tag with evaluateMode attribute'''
        '''If you would like to write next sentence:
           S1 and (S2 or S3) you have to create a solution container to every bracket with operator attribute and the [and,xor,default=or] value which represent the children solution relationship'''
        # if solution has evaluateMode attr
        if rs.getAttrValue(element,EVULATION_MODE_ATTR) is not None:
            requiredSolution = re.sub('\s+',' ',element.text).strip().lower()
            # get a tuple: channel output or error text, output is failed to the actual task?
            taskOutput =  self.channels.getChannelTaskOutput(rs.getAttrValue(element,SOLUTION_CH_NAME),rs.getAttrValue(task,TASK_ELEMENT_ID))
            # if parent task does not contain the output from channel which is referenced by actual solution
            if self.resultContent.get(element = task,tag = CH_OUT_TOTASK,attrName=SOLUTION_CH_NAME,attrValue=element.get(SOLUTION_CH_NAME),direct=True) is None:
                taskOutputElement = rs.createElement(CH_OUT_TOTASK, {SOLUTION_CH_NAME:rs.getAttrValue(element,SOLUTION_CH_NAME)})
                rs.setText(taskOutputElement, taskOutput[0] if taskOutput[1] else 'Error: '+ taskOutput[0])
                rs.appendTo(taskOutputElement,task)
            score = 0 if rs.getAttrValue(element,SCORE_ATTR) is None else float(rs.getAttrValue(element,SCORE_ATTR))
            try:
                # if channel output not failed to actual task
                if taskOutput[1]:
                    result = getattr(evaluateFunctions, rs.getAttrValue(element,EVULATION_MODE_ATTR))(taskOutput[0].lower(),requiredSolution,rs.getAttrValue(element,'evaluateArgs'))
                    # negate the result if solution has Negation attr
                    result = not result if rs.getAttrValue(element,'Negation') is not None else result
                    return (result,(score if result else 0),score)         
            except:
                self.logger.exception('Evaluate error in channel {} with {} taskID'.format(rs.getAttrValue(element,SOLUTION_CH_NAME),rs.getAttrValue(task,TASK_ELEMENT_ID)))
                rs.setAttr(element,TO_ELEMENT_ERROR_ATTR,'evaluateError')
                return (False,0,score)
            
            # set error to actual solution element
            rs.setAttr(element,TO_ELEMENT_ERROR_ATTR,'channelError')
            # return format: result [True,False], score to the result, max score
            return (False,0,score)

        # This section will run if element does not have evaluateMode attr
        results = []
        score = 0
        maxScore = 0
        # if operator is and AKEP give subscore and sum the solutions scores in the container
        # else max score will return calculated
        scoreFunc = sum if rs.getAttrValue(element,'operator') == 'and' else max
        for childSolution in self.resultContent.getAll(element=element, tag=SOLUTION_TAG, direct=True):
            # if element has children solition elements
            if scoreType is None or element.tag == TASKTAG and rs.getAttrValue(childSolution,SOL_SCORE_TYPE) == scoreType:
                result,scoreItem,maxScoreItem = self.solutionEvaluateAndPut(childSolution,task)
                score = scoreFunc([score,scoreItem if result else 0])
                maxScore = max(maxScore,maxScoreItem)
                rs.setAttr(childSolution,'result','true' if result else 'false')
                rs.setAttr(childSolution,'resultScore',self.formatScore(scoreItem))
                results.append(result)
        # default solution has or relationship with neighbour solutions
        # final result is calculated with multiOperations
        finalResult = self.multiOperations('or' if rs.getAttrValue(element,'operator') is None else rs.getAttrValue(element,'operator'), copy.copy(results))
        if element.tag == TASKTAG:
            finalResult = not finalResult if rs.getAttrValue(childSolution,'Negation') is not None else finalResult

        # if container tag has score and finalResult True it will be result else the children function score return  
        return (finalResult, (float(rs.getAttrValue(element,SCORE_ATTR)) if finalResult and rs.getAttrValue(element,SCORE_ATTR) is not None else score),maxScore)
        
    def multiOperations(self,opType,operands):
        '''Recursive function to process the sentence'''
        if len(operands) < 2:
            # only two operand is allow
            return False
        if len(operands) == 2:
            if opType == "or":
                return operands[0] or operands[1]
            elif opType == "and":
                return operands[0] and operands[1]
            elif opType == "xor":
                return operator.xor(operands[0],operands[1])
            else:
                raise AKEPException(ERROR['GENERAL']['NOT_SUPPORTER_SENT']+opType)
        leftOperand = operands.pop(0)
        rightOperand = self.multiOperations(opType,operands)
        return self.multiOperations(opType,[leftOperand,rightOperand])