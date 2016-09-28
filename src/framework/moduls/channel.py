from moduls.schemaSpecificAttr import *
from moduls.exceptions import *
from moduls.resultContent import resultContent as rs

import collections
import subprocess
import select

class channel:
    def __init__(self,resultContent, logger, InputChStreamValidFn, chStringValidFn):
        self.channels = collections.defaultdict(list)
        self.resultContent = resultContent
        self.logger = logger
        self.openList = []
        self.chStringValidFn = chStringValidFn

        for script in self.resultContent.getScripts():
            if CH_INPUT_TYPE in script:
                if script[CH_INPUT_TYPE] == SCRIPT_INPUT_TYPE[0]:
                    script[CH_INPUTSTREAM] = self.xmlTaskInputToList(self.resultContent.getAll(tag=CH_INPUTSTREAM,attrName=SOLUTION_CH_NAME,attrValue=script[CHANNEL_NAME_ATTR]))
                elif script[CH_INPUT_TYPE] == SCRIPT_INPUT_TYPE[1]:
                    if CH_PATH not in script:
                        raise AKEPException(ERROR['SCRIPT']['MISSING_PATH']+script[CHANNEL_NAME_ATTR])
                    data = openFileWithCheck(script[CH_PATH], self.logger, InputChStreamValidFn)
                    if data is None:
                        raise AKEPException(ERROR['GENERAL']['PERMISSON'] +'read file or '+ ERROR['FILE']['INVALID']+script[CH_PATH])
                    data = self.resultContent.keyBinding(data)
                    script[CH_INPUTSTREAM] = self.xmlTaskInputToList(self.resultContent.getAll(element=data, tag=TASKTAG))
                elif script[CH_INPUT_TYPE] == SCRIPT_INPUT_TYPE[2]:
                    if FROM_CAHNNEL not in script:
                        raise AKEPException(ERROR['SCRIPT']['NOT_VALID_VALUE'].format(FROM_CAHNNEL,script[CHANNEL_NAME_ATTR]))
                else:
                    raise AKEPException('Not valid value in "inputType" key from script: '+script[CHANNEL_NAME_ATTR])            
            if CH_INPUT_TYPE not in script or script[CH_INPUT_TYPE] == SCRIPT_INPUT_TYPE[2]:
                script[CH_INPUTSTREAM] = []
                for inputNode in self.resultContent.getAll(tag=CH_INPUTSTREAM,element=script['node'],direct=True):
                    script[CH_INPUTSTREAM].append(inputNode.text)
                if len(script[CH_INPUTSTREAM]) == 0:
                    del script[CH_INPUTSTREAM]
            self.channels[script[ENTRY_ATTR]].append(script)

    def xmlTaskInputToList(self,elements):
        inputs = []
        for inputNode in elements:
            taskID = rs.getAttrValue(rs.getParent(inputNode),TASK_ELEMENT_ID)
            children = rs.getChildren(inputNode)
            if len(children) == 0:
                inputs.append({'taskID':taskID,'input':rs.getText(inputNode)})
            else:
                inputstream = ''
                for child in children:
                    inputstream += rs.toStringFromElement(child).decode('utf-8')
                inputs.append({'taskID':taskID,'input':inputstream})
        return inputs

    def run(self):
        order = CH_ENTRY_ORDER
        for entry in order:
            for ch in self.channels[entry]:
                if entry == CH_ENTRY_ORDER[2] and NO_CONTINUE_AFTER_ERROR not in ch:
                    inputstream = SEPARATOR_COMMUNICATE_TASK_END.join(inputItem['input'] for inputItem in ch[CH_INPUTSTREAM])
                else:                            
                    inputstream = '\n'.join(ch[CH_INPUTSTREAM]) if CH_INPUTSTREAM in ch else None                
                
                if CH_INPUT_TYPE in ch and ch[CH_INPUT_TYPE] == SCRIPT_INPUT_TYPE[2]:
                    refChOut = self.getChannel(ch[FROM_CAHNNEL])
                    if refChOut == None or 'out' not in refChOut or refChOut['out'] == '':
                        raise AKEPException(ERROR['NOT_FIND']['CH_OR_CHOUT'].format(ch[FROM_CAHNNEL],ch[CHANNEL_NAME_ATTR]))
                    
                    if CH_INPUTTO in ch:
                        ch['arguments'] = ch['arguments'].replace(ch[CH_INPUTTO],refChOut['out'])
                    else:
                        inputstream = (inputstream+'\n'+refChOut['out']) if inputstream is not None else refChOut['out']
                        
                arguments = (ch[CH_PATH]+' '+ch['arguments']).split()
                ch['out'] = None
                again = True
                while again:
                    again = False
                    try:
                        self.logger.info('Channel {} start'.format(ch[CHANNEL_NAME_ATTR]))
                        self.logger.debug('Channel arguments: {} inputstream: {}'.format(ch['arguments'],inputstream))
                        if entry == CH_ENTRY_ORDER[1]:
                            proc = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
                            if inputstream is not None:                            
                                proc.stdin.write(inputstream)
                                proc.stdin.close()
                            poll_obj = select.poll()
                            if CH_CHAIN_CONT_COND in ch:
                                if ch[CH_CHAIN_CONT_COND] == CH_CHAIN_CONT_COND_TYPE[1]:                                    
                                    poll_obj.register(proc.stderr, select.POLLIN)
                                    if poll_obj.poll(CH_CON_TYPE_ANSWER_TIMEOUT):
                                        proc.stderr.readline()
                                    else:
                                        raise subprocess.TimeoutExpired(None,None)
                                elif ch[CH_CHAIN_CONT_COND] == CH_CHAIN_CONT_COND_TYPE[0]:
                                    poll_obj.register(proc.stdout, select.POLLIN)
                                    if poll_obj.poll(CH_CON_TYPE_ANSWER_TIMEOUT):
                                        proc.stdout.readline()
                                    else:
                                        raise subprocess.TimeoutExpired(None,None)
                            self.openList.append({'proc':proc,'chName':ch[CHANNEL_NAME_ATTR]})
                        else:
                            proc = subprocess.Popen(arguments,stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=subprocess.PIPE, universal_newlines=True)
                            self.openList.append({'proc':proc,'chName':ch[CHANNEL_NAME_ATTR]})
                            out, error = proc.communicate(input=inputstream,timeout=60)
                            self.logger.info('Channel {} stop'.format(ch[CHANNEL_NAME_ATTR]))
                            if error != '':
                                raise subprocess.SubprocessError(error)                            
                            ch['out'],lastRightIndex = self.createChannelOutputToTaskXML(ch[CH_INPUTSTREAM],out,ch['out']) if entry == CH_ENTRY_ORDER[2] else (out,None)
                            self.logger.debug('channel: {} out: {}'.format(ch[CHANNEL_NAME_ATTR], rs.toStringFromElement(ch['out']).decode('utf-8') if rs.isElementType(ch['out']) else ch['out']))                            
                    except FileNotFoundError:
                        self.terminateChannelScripts()
                        raise AKEPException(ERROR['FILE']['NOT_FIND']+ch[CHANNEL_NAME_ATTR])
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        raise AKEPException(ERROR['SCRIPT']['TIME_EXPIRED']+ ch[CHANNEL_NAME_ATTR])
                    except PermissionError:
                        raise AKEPException(ERROR['GENERAL']['PERMISSON'] + 'script: '+ch[CHANNEL_NAME_ATTR])
                    except (subprocess.SubprocessError, subprocess.CalledProcessError) as err:
                        if entry == CH_ENTRY_ORDER[2] and NO_CONTINUE_AFTER_ERROR not in ch:                        
                            self.logger.exception('Error in script: '+ch[CHANNEL_NAME_ATTR])
                            ch['out'], lastRightIndex = self.createChannelOutputToTaskXML(ch[CH_INPUTSTREAM],out,ch['out'])
                            ch['out'].append(rs.createElement(TASKTAG,{TO_ELEMENT_ERROR_ATTR:str(err),TASK_ELEMENT_ID:ch[CH_INPUTSTREAM][lastRightIndex+1]['taskID']}))
                            if lastRightIndex+1 < len(ch[CH_INPUTSTREAM])-1:
                                inputstream = SEPARATOR_COMMUNICATE_TASK_END.join([ch[CH_INPUTSTREAM][index]['input'] for index in range(lastRightIndex+2,len(ch[CH_INPUTSTREAM]))])
                                again = True
                        else:
                            raise AKEPException('Error in script: '+ ch[CHANNEL_NAME_ATTR])
        self.terminateChannelScripts()

    def getChannel(self,name):
        for entry in self.channels:
            for ch in self.channels[entry]:
                if ch[CHANNEL_NAME_ATTR] == name:
                    return ch
        raise AKEPException('Not find channel {}'.format(name))

    def getChannelTaskOutput(self,channelName,taskID):
        ch = self.getChannel(channelName)
        if rs.isElementType(ch['out']):
            task = self.resultContent.get(element=ch['out'], tag=TASKTAG, attrName='n', attrValue=taskID)
            if rs.getAttrValue(task,TO_ELEMENT_ERROR_ATTR) is not None:
                return rs.getAttrValue(task,TO_ELEMENT_ERROR_ATTR),False
            return rs.getText(task),True
        return ch['out'],True
                    
    def createChannelOutputToTaskXML(self,taskInputStream,xmlTextList,prevXML=None):
        if xmlTextList == '':
            return (prevXML,len(prevXML)-1) if prevXML is not None else (rs.createElement('tasks'),-1)
        tasks = xmlTextList.strip().strip(SEPARATOR_COMMUNICATE_TASK_END).split(SEPARATOR_COMMUNICATE_TASK_END)
        prevInd = len(rs.getChildren(prevXML)) if prevXML is not None else 0
        xmlText = '<tasks>'+''.join(['<task n="'+taskInputStream[prevInd+index]['taskID']+'"><![CDATA['+tasks[index]+']]></task>' for index in range(0,len(tasks))])+'</tasks>'
        tasksXML = self.chStringValidFn(xmlText)
        if prevXML is None:
            return (tasksXML, len(tasks)-1)
        for task in tasksXML:
            rs.appendTo(task,prevXML)
        return (prevXML,prevInd+len(tasks)-1)

    def terminateChannelScripts(self, killIt=False):
        if hasattr(self,'openList'):
            for item in self.openList:
                self.logger.debug('Channel: {} returnCode {}'.format(item['chName'],item['proc'].poll()))
                if item['proc'].poll() is None:
                    if killIt:
                        item['proc'].kill()
                        self.logger.info('Channel {} killed'.format(item['chName'])) 
                    else:
                        item['proc'].terminate()                
                        self.logger.info('Channel {} terminated'.format(item['chName']))
                if self.getChannel(item['chName'])[ENTRY_ATTR] == CH_ENTRY_ORDER[1]:
                    out, err = item['proc'].stdout.read(),item['proc'].stderr.read()
                    self.logger.debug('Channel: {} out: {} err: {}'.format(item['chName'],out,err))