# import AKEP moduls
from moduls.server import ThreadPoolTCPServer as evaluateRequestServer
from moduls.logger import AKEPLogger
from moduls.dataStore import dataStore
from moduls.exceptions import *
from moduls.evaluate import evaluate
from moduls.channel import channel
from moduls.resultContent import resultContent as rs
from moduls.schemaSpecificAttr import *
from moduls.analyse import analyse

import socketserver
import argparse
import json
import threading
import time
import os
import queue
from glob import iglob


class AKEPProcess():
    def __init__(self, command):
        self.command = command
        self.__lastState = 'init'
        self.exerciseRoots = {}
        self.exercisesPath = store.getValueFromKH(EXERCISE_PATH, self.command)

    def loadAllExercises(self, logger):
        for path in iglob(self.exercisesPath + '/' + EXERCISE_FILE_FORMAT):
            elementTreeObject = store.openFileWithCheck(path, store.checkExerciseValid)
            if elementTreeObject is not None:
                key = path.rsplit('.', 2)[1]
                self.exerciseRoots[key] = elementTreeObject.getroot()
                logger.info('Exercise loaded: ' + key)
            else:
                return (False, path)
        return (True, None)

    def run(self, logger, runningID):
        exerciseLoadSuccess = self.loadAllExercises(logger)
        if not exerciseLoadSuccess[0]:
            raise AKEPException(ERROR['FILE']['INVALID'] + exerciseLoadSuccess[1])

        self.exerciseID = store.getValueFromKH(EXERCISE_ID, self.command)
        self.ownerID = store.getValueFromKH(OWNER_ID, self.command)
        self.resultContent = store.createResultContent(self.exerciseID, self.ownerID, logger, runningID, self.command,
                                                       self.exerciseRoots)
        self.__lastState = 'Start [OK]'
        logger.info(self.__lastState)

        self.resultContent.referenceFormating()
        self.__lastState = 'References [OK]'
        logger.info(self.__lastState)

        self.resultContent.keyBinding()
        self.__lastState = 'Key binding [OK]'
        logger.info(self.__lastState)

        self.__channels = channel(self.resultContent, logger, store.checkTaskChannelInputStreamValid,
                                  store.checkTaskChannelStringValid, store.openFileWithCheck)
        self.__lastState = 'Channels initialize [OK]'
        logger.info(self.__lastState)

        self.openListKillFn = self.__channels.terminateChannelScripts
        self.__channels.run()
        self.__lastState = 'Channels run [OK]'
        logger.info(self.__lastState)

        self.__evaluateModul = evaluate(self.__channels.getChannelTaskOutput, self.resultContent, logger)
        self.__evaluateModul.run()
        self.__lastState = 'Evaluate all [OK]'
        logger.info(self.__lastState)

        self.resultContent.deleteNotOutTags()
        self.__lastState = 'Filter [OK]'
        logger.info(self.__lastState)

        return self.resultContent.toString()

    def getLastState(self):
        return self.__lastState

    def getAnalyseObjet(self):
        try:
            dummy = self.__channels
        except:
            return {'lastState': self.__lastState, 'chAnalyse': None, 'solAnalyse': None, 'taskAnalyse': None,
                    'score%': '0'}
        chAnalyse = []
        for chEntry in self.__channels.channels:
            for ch in self.__channels.channels[chEntry]:
                newAnalyseObj = []
                for key in ANALYSE_CH_PROP:
                    newAnalyseObj.append(ch[key] if key in ch else '')
                chAnalyse.append(newAnalyseObj)
        try:
            dummy = self.__evaluateModul
        except:
            return {'lastState': self.__lastState, 'chAnalyse': chAnalyse, 'solAnalyse': None, 'taskAnalyse': None,
                    'score%': '0'}
        return {'lastState': self.__lastState, 'chAnalyse': chAnalyse, 'solAnalyse': self.__evaluateModul.toAnalyse,
                'taskAnalyse': self.__evaluateModul.taskAnalyse, 'score%': self.__evaluateModul.scoreToAnalyse}


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        runningID = threading.current_thread().name.split('-')[1]

        globalLogger = AKEPLogger.getLogger(runningID)
        globalLogger.info('New connection: ' + str(self.request.getpeername()))
        start = time.time()

        errorType = ''

        try:
            data = self.request.recv(1024).strip()
            command = json.loads(data.decode('utf-8'))
            if 'get' in command:
                if command['get'] == 'status' and 'timeStamp' in command and command[
                    'timeStamp'] in asyncWorkerAnswerStates:
                    status = asyncWorkerAnswerStates[command['timeStamp']]()
                    resultXMLRoot = rs.createElement(EXERCISE, {'status': status})
                    self.request.sendall(rs.toStringFromElement(resultXMLRoot))
                return

            timestamp = store.getValueFromKH('timeStamp', command)
            akepProcess = AKEPProcess(command)

            if 'async' in command and asyncWorkerQueue:
                globalLogger.info('Async answer type')
                akepProcess.globalLogger = globalLogger
                asyncWorkerQueue.put(akepProcess)
                globalLogger.info('Connection closed')
                return
            else:
                fullLogPath = logpath + '/' + timestamp + '-' + runningID + '.log'
                globalLogger.info('Detail log: ' + fullLogPath)
                logger = AKEPLogger.initialize(fullLogPath, runningID)
                self.request.sendall(akepProcess.run(logger, runningID))
        except AKEPException as err:
            # create an empty exercise element with error text from the exception
            errorType = str(err).replace(',', ' ')
            resultXMLRoot = rs.createElement(EXERCISE, {TO_ELEMENT_ERROR_ATTR: str(err),
                                                        'exerciseID': akepProcess.exerciseID if hasattr(akepProcess,
                                                                                                        'exerciseID') else 'undefined',
                                                        'ownerID': akepProcess.ownerID if hasattr(akepProcess,
                                                                                                  'ownerID') else 'undefined'})
            self.request.sendall(rs.toStringFromElement(resultXMLRoot))
            logger.exception(ERROR['GENERAL']['AKEP_REQUIRED_FAIL'])
        except Exception as err:
            errorType = str(err).replace(',', ' ')
            try:
                try:
                    resultXMLRoot = rs.createElement(EXERCISE, {TO_ELEMENT_ERROR_ATTR: str(err),
                                                                'exerciseID': akepProcess.exerciseID if hasattr(
                                                                    akepProcess, 'exerciseID') else 'undefined',
                                                                'ownerID': akepProcess.ownerID if hasattr(akepProcess,
                                                                                                          'ownerID') else 'undefined'})
                except UnboundLocalError:
                    resultXMLRoot = rs.createElement(EXERCISE,
                                                     {TO_ELEMENT_ERROR_ATTR: str(err), 'exerciseID': 'undefined',
                                                      'ownerID': 'undefined'})
                self.request.sendall(rs.toStringFromElement(resultXMLRoot))
            except:
                logger.exception(ERROR['UNEXPECTED']['SOCKET_CLOSE'])

        stop = time.time()

        if 'akepProcess' in locals():
            AKEPClear(akepProcess, globalLogger)

        try:
            akepProcAnalyseObj = akepProcess.getAnalyseObjet()
            genAnalyseObj = {'exID': command[EXERCISE_ID], 'ownerID': command[OWNER_ID],
                             'FolderID': store.getValueFromKH('timeStamp', command) + '-' + runningID, 'start': start,
                             'stop': stop, 'lastState': akepProcAnalyseObj['lastState'], 'errorType': errorType,
                             'score%': akepProcAnalyseObj['score%']}
            analyseObj = analyse(genAnalyseObj, akepProcAnalyseObj, store.getValueFromKH('analyseFolder', command))
            analyseObj.run()
        except UnboundLocalError:
            pass
        except:
            logger.exception('Analyse failed')
        globalLogger.info('Connection closed')


def AKEPClear(akepProcess, globalLogger):
    try:
        if hasattr(akepProcess, 'resultContent'):
            akepProcess.resultContent.giveBackUser()
        if hasattr(akepProcess, 'openListKillFn'):
            akepProcess.openListKillFn(True)
    except UnboundLocalError:
        pass
    except:
        globalLogger.warning('Can not give back the user to the pool or can not close a process')


def asyncWorker():
    global asyncWorkerAnswerStates
    while True:
        akepProcess = asyncWorkerQueue.get()
        runningID = threading.current_thread().name.split('-')[1]

        asyncAnswerPath = store.getValueFromKH(SOLTARGET, akepProcess.command)
        timestamp = store.getValueFromKH('timeStamp', akepProcess.command)

        fullLogPath = asyncAnswerPath + '/' + timestamp
        os.makedirs(fullLogPath)
        logger = AKEPLogger.initialize(fullLogPath + '/result.log', 'A-1' + runningID)
        writePath = asyncAnswerPath + '/' + timestamp + '/result.xml'

        asyncWorkerAnswerStatesLock.acquire()
        asyncWorkerAnswerStates[timestamp] = akepProcess.getLastState
        asyncWorkerAnswerStatesLock.release()

        try:
            result = akepProcess.run(logger, runningID)
        except Exception as err:
            logger.exception('Async answer failed')
            resultXMLRoot = rs.createElement(EXERCISE, {TO_ELEMENT_ERROR_ATTR: str(err),
                                                        'exerciseID': akepProcess.exerciseID if hasattr(akepProcess,
                                                                                                        'exerciseID') else 'undefined',
                                                        'ownerID': akepProcess.ownerID if hasattr(akepProcess,
                                                                                                  'ownerID') else 'undefined'})
            result = rs.toStringFromElement(resultXMLRoot)

        AKEPClear(akepProcess, akepProcess.globalLogger)

        with open(writePath, 'wb') as f:
            f.write(result)

        asyncWorkerAnswerStatesLock.acquire()
        asyncWorkerAnswerStates.pop(timestamp, None)
        asyncWorkerAnswerStatesLock.release()

        asyncWorkerQueue.task_done()


def main():
    global store, logpath, asyncWorkerQueue, asyncWorkerAnswerStates, asyncWorkerAnswerStatesLock

    parser = argparse.ArgumentParser('AKEP')
    parser.add_argument('-p', '--path', metavar='PATH', help="AKEP local configuration file's path",
                        default='akep.local.cfg', type=str)
    parser.add_argument('-l', '--logger', metavar='PATH', help="AKEP logger file's name", default='akep.log', type=str)
    parser.add_argument('-s', '--schema', metavar='PATH', help="AKEP exercise descriptor schema file's path",
                        default='../schema/akep-exercises.xsd', type=str)
    parser.add_argument('-c', '--chSchema', metavar='PATH', help="AKEP channel output schema file's path",
                        default='../schema/akep-XMLChannel.xsd', type=str)

    args = parser.parse_args()

    logpath = './log'
    if not os.path.exists(logpath):
        os.makedirs(logpath)
    logger = AKEPLogger.initialize(logpath + '/' + args.logger)
    logger.info('AKEP started')

    store = dataStore(args.path, args.schema, logger, args.chSchema)

    if store.isReady():
        if store.getValueFromKH(ASYNCANSWER):
            asyncWorkerQueue = queue.Queue()
            asyncWorkerAnswerStates = {}
            asyncWorkerAnswerStatesLock = threading.Lock()
            for i in range(store.getValueFromKH(ASYNCANSWER_NUM)):
                t = threading.Thread(target=asyncWorker)
                t.daemon = True
                t.start()
            logger.info('Async answer active')
        try:
            # Create server pool with asynchronous handler
            server = evaluateRequestServer((store.getValueFromKH(HOST), store.getValueFromKH(PORT)),
                                           ThreadedTCPRequestHandler)
            # Start server in main thread
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            server_thread.join()
            if asyncWorkerQueue:
                asyncWorkerQueue.join()
        except (KeyboardInterrupt, SystemExit):
            server.shutdown()
            logger.info('Wait for server threads')
            server.join()
            if store.getValueFromKH(ASYNCANSWER):
                logger.info('Wait for worker threads')
                asyncWorkerQueue.join()
            server.server_close()
        except:
            logger.exception(ERROR['UNEXPECTED']['AKEP_STOP'])

    logger.info('AKEP stopped')


if __name__ == "__main__":
    main()
