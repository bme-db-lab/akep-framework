
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

class AKEPProcess():
    def __init__(self, command, logger, runningID):
        self.runningID = runningID  
        self.logger = logger
        self.command = command
        self.__lastState = 'init'
    
    def run(self):
        self.exerciseID = store.getValueFromKH(EXERCISE_ID,self.command)
        self.ownerID = store.getValueFromKH(OWNER_ID,self.command)
        self.resultContent = store.createResultContent(self.exerciseID,self.ownerID, self.logger, self.runningID, self.command)
        self.__lastState = 'Start [OK]'
        self.logger.info(self.__lastState)

        self.resultContent.referenceFormating()
        self.__lastState = 'References [OK]'
        self.logger.info(self.__lastState)

        self.resultContent.keyBinding()
        self.__lastState = 'Key binding [OK]'
        self.logger.info(self.__lastState)

        self.__channels = channel(self.resultContent, self.logger, store.checkTaskChannelInputStreamValid,store.checkTaskChannelStringValid, store.openFileWithCheck)
        self.__lastState = 'Channels initialize [OK]'
        self.logger.info(self.__lastState)

        self.resultContent.deleteNotOutTags()
        self.__lastState = 'Delete unused tags from output [OK]'
        self.logger.info(self.__lastState)

        self.openListKillFn = self.__channels.terminateChannelScripts
        self.__channels.run()
        self.__lastState = 'Channels run [OK]'
        self.logger.info(self.__lastState)

        self.__evaluateModul = evaluate(self.__channels,self.resultContent, self.logger)
        self.__evaluateModul.run()
        self.__lastState = 'Evaluate all [OK]'
        self.logger.info(self.__lastState)

        return self.resultContent.toString()
    
    def getAnalyseObjet(self):
        try:
            dummy = self.__channels
        except:
            return {'lastState': self.__lastState, 'chAnalyse':None, 'solAnalyse': None, 'taskAnalyse':None}
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
            return {'lastState': self.__lastState, 'chAnalyse':chAnalyse, 'solAnalyse': None, 'taskAnalyse':None}
        return {'lastState': self.__lastState, 'chAnalyse':chAnalyse, 'solAnalyse': self.__evaluateModul.toAnalyse, 'taskAnalyse':self.__evaluateModul.taskAnalyse}
    

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        runningID = threading.current_thread().name.split('-')[1]
        logger = AKEPLogger.getLogger(runningID)
        logger.info('New connection: '+str(self.request.getpeername()))
        start = time.time()
        errorType = ''
        try:
            data = self.request.recv(1024).strip()
            command = json.loads(data.decode('utf-8'))
            akepProcess = AKEPProcess(command, logger, runningID)
            self.request.sendall(akepProcess.run())            
        except AKEPException as err:
            # create an empty exercise element with error text from the exception
            errorType = str(err).replace(',',' ')
            resultXMLRoot = rs.createElement(EXERCISE, {TO_ELEMENT_ERROR_ATTR: str(err),'exerciseID': akepProcess.exerciseID if hasattr(akepProcess,'exerciseID') else 'undefined', 'ownerID': akepProcess.ownerID if hasattr(akepProcess,'ownerID') else 'undefined'})
            self.request.sendall(rs.toStringFromElement(resultXMLRoot))
            logger.exception(ERROR['GENERAL']['AKEP_REQUIRED_FAIL'])
        except Exception as err:
            errorType = str(err).replace(',',' ')
            try: 
                resultXMLRoot = rs.createElement(EXERCISE, {TO_ELEMENT_ERROR_ATTR: str(err),'exerciseID': akepProcess.exerciseID if hasattr(akepProcess,'exerciseID') else 'undefined', 'ownerID': akepProcess.ownerID if hasattr(akepProcess,'ownerID') else 'undefined'})
                self.request.sendall(rs.toStringFromElement(resultXMLRoot))
            except:
                logger.exception('Send error failed')
                pass
            logger.exception(ERROR['UNEXPECTED']['SOCKET_CLOSE'])
        stop = time.time()
        if hasattr(akepProcess,'resultContent'):
            akepProcess.resultContent.giveBackUser()
        if hasattr(akepProcess,'openListKillFn'):
            akepProcess.openListKillFn(True)
        logger.info('Connetion closed')
        try:
            akepProcAnalyseObj = akepProcess.getAnalyseObjet()
            genAnalyseObj = {'exID':command[EXERCISE_ID],'ownerID':command[OWNER_ID],'FolderID':store.getValueFromKH('timeStamp',command)+'-'+runningID,'start':start,'stop':stop,'lastState': akepProcAnalyseObj['lastState'], 'errorType':errorType}
            analyseObj = analyse(genAnalyseObj,akepProcAnalyseObj, store.getValueFromKH('analyseFolder',command))
            analyseObj.run()
        except:
            logger.exception('Analyse failed')
def main():
    global store
    
    parser = argparse.ArgumentParser('AKEP')
    parser.add_argument('-p','--path', metavar='PATH', help="AKEP local configuration file's path", default='akep.local.cfg', type=str)
    parser.add_argument('-l','--logger', metavar='PATH', help="AKEP logger file's path", default='akep.log', type=str)
    parser.add_argument('-s','--schema', metavar='PATH', help="AKEP exercise descriptor schema file's path", default='../schema/akep-exercises.xsd', type=str)
    parser.add_argument('-c','--chSchema', metavar='PATH', help="AKEP channel output schema file's path", default='../schema/akep-XMLChannel.xsd', type=str)
    
    args = parser.parse_args()

    logger = AKEPLogger.initialize(args.logger)
    logger.info('AKEP started')

    store = dataStore(args.path,args.schema,logger, args.chSchema)

    if store.isReady():
        try:
            # Create server pool with asynchronous handler
            server = evaluateRequestServer((store.getValueFromKH(HOST), store.getValueFromKH(PORT)), ThreadedTCPRequestHandler)
            # Start server in main thread
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            server_thread.join()
        except (KeyboardInterrupt, SystemExit):
            server.shutdown()
            logger.info('Wait for worker thread')
            server.join()            
            server.server_close()
        except:
            logger.exception(ERROR['UNEXPECTED']['AKEP_STOP'])

    logger.info('AKEP stopped')

if __name__ == "__main__":
    main()    
