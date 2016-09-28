
# import AKEP moduls
from moduls.server import ThreadPoolTCPServer as evaluateRequestServer
from moduls.logger import AKEPLogger
from moduls.dataStore import dataStore
from moduls.exceptions import *
from moduls.evaluate import evaluate
from moduls.channel import channel
from moduls.resultContent import resultContent as rs
from moduls.schemaSpecificAttr import *


import socketserver
import argparse
import json
import threading

class AKEPProcess():
    def __init__(self, command, logger, runningID):
        self.runningID = runningID  
        self.logger = logger
        self.command = command
    
    def run(self):
        self.exerciseID = store.getValueFromKH(EXERCISE_ID,self.command)
        self.ownerID = store.getValueFromKH(OWNER_ID,self.command)
        resultContent = store.createResultContent(self.exerciseID,self.ownerID, self.logger, self.runningID, self.command)
        self.logger.info('Start [OK]')

        resultContent.referenceFormating()
        self.logger.info('References [OK]')

        resultContent.keyBinding()
        self.logger.info('Key binding [OK]')

        channels = channel(resultContent, self.logger, store.checkTaskChannelInputStreamValid,store.checkTaskChannelStringValid)
        self.logger.info('Channels initialize [OK]')

        resultContent.deleteNotOutTags()
        self.logger.info('Delete unused tags from output [OK]')

        channels.run()
        self.openListKillFn = channels.terminateChannelScripts
        self.logger.info('Channels run [OK]')

        evaluateModul = evaluate(channels,resultContent, self.logger)
        evaluateModul.run()
        self.logger.info('Evaluate all [OK]')

        return resultContent.toString()
    

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        runningID = threading.current_thread().name.split('-')[1]
        logger = AKEPLogger.getLogger(runningID)
        logger.info('New connection: '+str(self.request.getpeername()))
        try:
            data = self.request.recv(1024).strip()
            command = json.loads(data.decode('utf-8'))
            akepProcess = AKEPProcess(command, logger, runningID)
            self.request.sendall(akepProcess.run())            
        except AKEPException as err:
            # create an empty exercise element with error text from the exception
            resultXMLRoot = rs.createElement(EXERCISE, {TO_ELEMENT_ERROR_ATTR: str(err),'exerciseID': akepProcess.exerciseID if hasattr(akepProcess,'exerciseID') else 'undefined', 'ownerID': akepProcess.ownerID if hasattr(akepProcess,'ownerID') else 'undefined'})
            self.request.sendall(rs.toStringFromElement(resultXMLRoot))
            logger.exception(ERROR['GENERAL']['AKEP_REQUIRED_FAIL'])
        except Exception as err:
            try: 
                resultXMLRoot = rs.createElement(EXERCISE, {TO_ELEMENT_ERROR_ATTR: str(err),'exerciseID': akepProcess.exerciseID if hasattr(akepProcess,'exerciseID') else 'undefined', 'ownerID': akepProcess.ownerID if hasattr(akepProcess,'ownerID') else 'undefined'})
                self.request.sendall(rs.toStringFromElement(resultXMLRoot))
            except:
                pass
            logger.exception(ERROR['UNEXPECTED']['SOCKET_CLOSE'])
        if hasattr(akepProcess,'user'):
            giveBackUser(akepProcess.usergroup,akepProcess.user)
        if hasattr(akepProcess,'openListKillFn'):
            akepProcess.openListKillFn(True)
        logger.info('Connetion closed')
        # TODO ANALIZE

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
