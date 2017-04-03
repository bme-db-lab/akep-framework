from moduls.schemaSpecificAttr import *
from moduls.exceptions import *
from moduls.resultContent import resultContent as rs

import collections
import subprocess
import select
import re
import time

'''
Channel Modul
This modul can initialize channels and run it base on resultcontent.getScripts()
openFileWithCheckFn : function reference to dataStore's instance's openFileWithCheck function
'''


class channel:
    def __init__(self, resultContent, logger, InputChStreamValidFn, chStringValidFn, openFileWithCheckFn):
        """
        Initialize channels width fill inputstreams
        """
        self.channels = collections.defaultdict(list)
        self.resultContent = resultContent
        self.logger = logger
        self.openList = []
        # input channel schema validation function reference
        self.chStringValidFn = chStringValidFn

        for script in self.resultContent.getScripts():
            if CH_INPUT_TYPE in script:
                if script[CH_INPUT_TYPE] == SCRIPT_INPUT_TYPE[0]:
                    # inputstream from exercise.X.xml object's tasks
                    script['taskInput'] = self.__xmlTaskInputToList(
                        self.resultContent.getAll(tag=CH_INPUTSTREAM, attrName=SOLUTION_CH_NAME,
                                                  attrValue=script[CHANNEL_NAME_ATTR]))
                elif script[CH_INPUT_TYPE] == SCRIPT_INPUT_TYPE[1]:
                    if CH_EXT_PATH not in script:
                        raise AKEPException(ERROR['SCRIPT']['MISSING_PATH'] + script[CHANNEL_NAME_ATTR])
                    # load external file data ..
                    data = openFileWithCheckFn(script[CH_EXT_PATH], InputChStreamValidFn)
                    if data is None:
                        raise AKEPException(
                            ERROR['GENERAL']['PERMISSON'] + 'read file or ' + ERROR['FILE']['INVALID'] + script[
                                CH_EXT_PATH])
                    # .. with binding keys
                    data = self.resultContent.keyBinding(data)
                    # .. to inputstream
                    script['taskInput'] = self.__xmlTaskInputToList(
                        self.resultContent.getAll(element=data, tag=TASKTAG, attrName=TASK_ELEMENT_ID), False)
                elif script[CH_INPUT_TYPE] == SCRIPT_INPUT_TYPE[2]:
                    if FROM_CAHNNEL not in script:
                        # if inputType is fromChannel and script tag does not has sourceChannel attr
                        raise AKEPException(
                            ERROR['SCRIPT']['NOT_VALID_VALUE'].format(FROM_CAHNNEL, script[CHANNEL_NAME_ATTR]))
                else:
                    # no exist inputType
                    raise AKEPException(
                        ERROR['SCRIPT']['NOT_VALID_VALUE'].format('inputType', script[CHANNEL_NAME_ATTR]))

            # channel inner inputstream used to write initial content before taskInput, after script error this content will use as input again
            # and taskInput start after the error phase
            script[CH_INPUTSTREAM] = []
            for inputNode in self.resultContent.getAll(tag=CH_INPUTSTREAM, element=script['node'], direct=True):
                script[CH_INPUTSTREAM].append(inputNode.text)
            if len(script[CH_INPUTSTREAM]) == 0:
                del script[CH_INPUTSTREAM]
            self.channels[script[ENTRY_ATTR]].append(script)

    def __xmlTaskInputToList(self, elements, inlineType=True):
        """
        If you use inputstream in tasks and there is at least one channel which has inner inputType,
        this function will convert these inputstreams to channel inputstream
        """
        inputs = []
        for inputNode in elements:
            taskID = rs.getAttrValue(rs.getParent(inputNode) if inlineType else inputNode, TASK_ELEMENT_ID)
            children = rs.getChildren(inputNode)
            if len(children) == 0:
                # only text
                inputs.append({'taskID': taskID, 'input': rs.getText(inputNode)})
            elif inlineType:
                # contain elements
                inputstream = ''
                for child in children:
                    inputstream += rs.toStringFromElement(child).decode('utf-8')
                inputs.append({'taskID': taskID, 'input': inputstream})
        return inputs

    def run(self):
        """
        Run all channels in definied order
        """
        order = CH_ENTRY_ORDER
        for entry in order:
            for ch in self.channels[entry]:
                # create taskinput and inputstream
                if 'taskInput' in ch:
                    taskInput = SEPARATOR_COMMUNICATE_TASK_END.join(inputItem['input'] for inputItem in ch['taskInput'])
                inputstream = '\n'.join(ch[CH_INPUTSTREAM]) if CH_INPUTSTREAM in ch else ''

                if CH_INPUT_TYPE in ch and ch[CH_INPUT_TYPE] == SCRIPT_INPUT_TYPE[2]:
                    refChOut = self.__getChannel(ch[FROM_CAHNNEL])
                    if refChOut == None or 'out' not in refChOut or refChOut['out'] == '':
                        raise AKEPException(
                            ERROR['NOT_FOUND']['CH_OR_CHOUT'].format(ch[FROM_CAHNNEL], ch[CHANNEL_NAME_ATTR]))
                    output = str(refChOut['out'])
                    if CH_INPUTTO in ch:
                        ch['arguments'] = ch['arguments'].replace(ch[CH_INPUTTO], output)
                        if inputstream != '':
                            inputstream = inputstream.replace(ch[CH_INPUTTO], output)
                    else:
                        inputstream = (inputstream + '\n' + output) if inputstream != '' else output

                concatInnerInputToTaskInp = '' if inputstream == '' else inputstream + SEPARATOR_COMMUNICATE_TASK_END

                arguments = (ch[CH_PATH] + ' ' + ch['arguments']).split()
                ch['out'] = None
                ch['error'] = None
                again = True
                while again:
                    again = False
                    ch['errorType'] = ''
                    ch['start'] = str(time.time())
                    try:
                        self.logger.info('Channel {} start'.format(ch[CHANNEL_NAME_ATTR]))
                        self.logger.debug('Channel arguments: {} inputstream: {}'.format(ch['arguments'],
                                                                                         inputstream if 'taskInput' not in ch else (
                                                                                             concatInnerInputToTaskInp + taskInput)))
                        if entry == CH_ENTRY_ORDER[1]:
                            proc = subprocess.Popen(' '.join(arguments) if CHANNEL_WITH_SHELL in ch else arguments,
                                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE, universal_newlines=True,
                                                    shell=CHANNEL_WITH_SHELL in ch)
                            if inputstream != '':
                                proc.stdin.write(inputstream)
                                proc.stdin.close()
                            poll_obj = select.poll()
                            result = ''
                            # con type can trigger the next item in chain if channel has CH_CHAIN_CONT_COND
                            if CH_CHAIN_CONT_COND in ch:
                                if ch[CH_CHAIN_CONT_COND] == CH_CHAIN_CONT_COND_TYPE[1]:
                                    poll_obj.register(proc.stderr, select.POLLIN)
                                    if poll_obj.poll(CH_CON_TYPE_ANSWER_TIMEOUT):
                                        result = proc.stderr.readline()
                                    else:
                                        raise subprocess.TimeoutExpired(None, None)
                                elif ch[CH_CHAIN_CONT_COND] == CH_CHAIN_CONT_COND_TYPE[0]:
                                    poll_obj.register(proc.stdout, select.POLLIN)
                                    if poll_obj.poll(CH_CON_TYPE_ANSWER_TIMEOUT):
                                        result = proc.stdout.readline()
                                    else:
                                        raise subprocess.TimeoutExpired(None, None)
                            self.openList.append({'proc': proc, 'chName': ch[CHANNEL_NAME_ATTR], 'entry': entry})
                            if proc.poll() is not None or 'error' in result.lower() or 'traceback' in result.lower():
                                raise subprocess.SubprocessError('Contionous channel is dead')
                        else:
                            # run subprocess
                            proc = subprocess.Popen(' '.join(arguments) if CHANNEL_WITH_SHELL in ch else arguments,
                                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE, universal_newlines=True,
                                                    shell=CHANNEL_WITH_SHELL in ch)
                            self.openList.append({'proc': proc, 'chName': ch[CHANNEL_NAME_ATTR], 'entry': entry})
                            out, error = proc.communicate(input=(
                                inputstream if 'taskInput' not in ch else (concatInnerInputToTaskInp + taskInput)),
                                timeout=60)
                            self.logger.info('Channel {} stop'.format(ch[CHANNEL_NAME_ATTR]))
                            if proc.poll() != 0:
                                raise subprocess.SubprocessError(error)
                            if CH_OUT_TASK_TYPE in ch:
                                ch['out'] = self.chStringValidFn(re.sub('set feedback (on|off)', '',
                                                                        re.sub('(?!--#)--.*\n', '', out[out.find(
                                                                            '<tasks>'):out.find(
                                                                            '</tasks>') + 8].replace('prompt', '')),
                                                                        flags=re.DOTALL))
                            else:
                                ch['out'], lastRightIndex = self.__createChannelOutputToTaskXML(ch['taskInput'], out,
                                                                                                ch['out'],
                                                                                                concatInnerInputToTaskInp) if 'taskInput' in ch else (
                                    out, None)
                                ch['error'], nothing = self.__createChannelOutputToTaskXML(ch['taskInput'], error,
                                                                                           ch['error'],
                                                                                           concatInnerInputToTaskInp) if 'taskErrorHandle' in ch else (
                                    error, None)
                            self.logger.debug('channel: {} out: {}'.format(ch[CHANNEL_NAME_ATTR],
                                                                           rs.toStringFromElement(ch['out']).decode(
                                                                               'utf-8') if rs.isElementType(
                                                                               ch['out']) else ch['out']))
                            if ch['error'] is not None:
                                self.logger.debug('channel: {} error out: {}'.format(ch[CHANNEL_NAME_ATTR],
                                                                                     rs.toStringFromElement(
                                                                                         ch['error']).decode(
                                                                                         'utf-8') if rs.isElementType(
                                                                                         ch['error']) else ch['error']))
                    except FileNotFoundError:
                        ch['stop'] = str(time.time())
                        ch['errorType'] = 'Script not found'
                        self.terminateChannelScripts()
                        raise AKEPException(ERROR['FILE']['NOT_FOUND'] + ch[CHANNEL_NAME_ATTR])
                    except subprocess.TimeoutExpired:
                        ch['errorType'] = 'Channel time out'
                        ch['stop'] = str(time.time())
                        proc.kill()
                        raise AKEPException(ERROR['SCRIPT']['TIME_EXPIRED'] + ch[CHANNEL_NAME_ATTR])
                    except PermissionError:
                        ch['stop'] = str(time.time())
                        raise AKEPException(ERROR['GENERAL']['PERMISSON'] + 'script: ' + ch[CHANNEL_NAME_ATTR])
                    except (subprocess.SubprocessError, subprocess.CalledProcessError) as err:
                        if 'taskInput' in ch:
                            ch['errorType'] = '[ReRUN] Call- or subprocess error'
                            self.logger.exception('Error in script: ' + ch[CHANNEL_NAME_ATTR])
                            # create new run envirement with the content after error
                            ch['out'], lastRightIndex = self.__createChannelOutputToTaskXML(ch['taskInput'], out,
                                                                                            ch['out'],
                                                                                            concatInnerInputToTaskInp)
                            ch['out'].append(rs.createElement(TASKTAG, {TO_ELEMENT_ERROR_ATTR: str(err),
                                                                        TASK_ELEMENT_ID:
                                                                            ch['taskInput'][lastRightIndex + 1][
                                                                                'taskID']}))
                            if 'taskErrorHandle' in ch:
                                ch['error'] = self.__createChannelOutputToTaskXML(ch['taskInput'], str(err),
                                                                                  ch['error'],
                                                                                  concatInnerInputToTaskInp)
                                errorTag, nothing = rs.createElement(TASKTAG, {
                                    TASK_ELEMENT_ID: ch['taskInput'][lastRightIndex + 1]['taskID']})
                                ch['error'].append(errorTag)
                            if lastRightIndex + 1 < len(ch[
                                                            'taskInput']) - 1 and NO_CONTINUE_AFTER_ERROR not in ch and 'CRITICAL' not in str(
                                err):
                                taskInput = SEPARATOR_COMMUNICATE_TASK_END.join(
                                    [ch['taskInput'][index]['input'] for index in
                                     range(lastRightIndex + 2, len(ch['taskInput']))])
                                again = True
                        else:
                            self.logger.error(str(err))
                            ch['errorType'] = 'Call- or subprocess error'
                            ch['stop'] = str(time.time())
                            raise AKEPException('Error in script: ' + ch[CHANNEL_NAME_ATTR])
                    ch['stop'] = str(time.time())
        self.terminateChannelScripts()

    def __getChannel(self, name):
        for entry in self.channels:
            for ch in self.channels[entry]:
                if ch[CHANNEL_NAME_ATTR] == name:
                    return ch
        raise AKEPException('Not found channel {}'.format(name))

    def getChannelTaskOutput(self, channelName, taskID, shouldError):
        """
        Public function to get channel task content
        return: text content, shouldError if it was an error else not shouldError
        """
        ch = self.__getChannel(channelName)
        if rs.isElementType(ch['out']):
            # first try check error output from ch['error'] in case of preprocessor handle the errors
            if 'taskErrorHandle' in ch and shouldError:
                errorToTask = self.resultContent.get(element=ch['error'], tag=TASKTAG, attrName='n', attrValue=taskID)
                if errorToTask is not None:
                    return (rs.getText(errorToTask), shouldError)

            task = self.resultContent.get(element=ch['out'], tag=TASKTAG, attrName='n', attrValue=taskID)
            if task is None:
                return (None, shouldError)
            # .. try check the errors which are catched by AKEP
            if rs.getAttrValue(task, TO_ELEMENT_ERROR_ATTR) is not None:
                return rs.getAttrValue(task, TO_ELEMENT_ERROR_ATTR), shouldError
            # final there was not error
            return (rs.getText(task), not shouldError)
        return (ch['out'], True)

    def __createChannelOutputToTaskXML(self, taskInputStream, xmlTextList, prevXML, concatInnerInputToTaskInp):
        """
        Create channel (xml format) output from separated plain text
        Handle: error state with result second parameter
        return: xml format tasks output, valid last task index from taskInputStream
        """
        tasks = xmlTextList.strip().rstrip(SEPARATOR_COMMUNICATE_TASK_END).split(SEPARATOR_COMMUNICATE_TASK_END)

        if concatInnerInputToTaskInp != '' and len(tasks) > 0:
            # delete the output which belong to the initial inputstream (if it exist)
            del tasks[0]
        if len(tasks) == 0 or tasks[0] == '':
            # return only prevXML if no new content after error
            return (prevXML, len(prevXML) - 1) if prevXML is not None else (rs.createElement('tasks'), -1)

        prevInd = len(prevXML) if prevXML is not None else 0

        try:
            xmlText = '<tasks>' + ''.join(
                ['<task n="' + taskInputStream[prevInd + index]['taskID'] + '"><![CDATA[' + tasks[index] + ']]></task>'
                 for index in range(0, len(tasks))]) + '</tasks>'
        except IndexError as err:
            self.logger.debug(
                'PrevInd:{}\nrequiredTaskLen:{}\nTaskLen{}\nTasks{}'.format(prevInd, len(taskInputStream), len(tasks),
                                                                            '\n---------------'.join(tasks)))
            raise AKEPException(str(err))

        # create result xml if it valid channel output
        tasksXML = self.chStringValidFn(xmlText)

        # return result xml, last valid index
        if prevXML is None:
            return (tasksXML, len(tasks) - 1)
        for task in tasksXML:
            rs.appendTo(task, prevXML)
        return (prevXML, prevInd + len(tasks) - 1)

    def terminateChannelScripts(self, killIt=False):
        """
        Public function to terminate/kill openned subprocessors
        """
        if hasattr(self, 'openList'):
            for item in self.openList:
                if not killIt:
                    self.logger.debug('Channel: {} returnCode {}'.format(item['chName'], item['proc'].poll()))
                if item['proc'].poll() is None:
                    if killIt:
                        item['proc'].kill()
                        self.logger.info('Channel {} killed'.format(item['chName']))
                    else:
                        item['proc'].terminate()
                        self.logger.info('Channel {} terminated'.format(item['chName']))
