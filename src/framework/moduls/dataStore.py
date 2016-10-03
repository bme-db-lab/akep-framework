from moduls.schemaSpecificAttr import *
from moduls.exceptions import *
from moduls.resultContent import resultContent
import os
from lxml import etree
import json
from glob import iglob
import collections
import threading

# moduls to use eval
import time

class dataStore:
    lock = threading.Lock()

    def __init__(self, localConfigFile, schemaFile, logger, channelScemaFile = None):
        self.logger = logger
        self.globalConf = self.openFileWithCheck(os.path.dirname(os.path.realpath(__file__))+"/../"+GLOBAL_CONF_FILE,json.load)
        self.localConf = self.openFileWithCheck(localConfigFile,json.load)
        self.schema = self.openFileWithCheck(schemaFile,etree.parse)
        chSchema = None if channelScemaFile is None else self.openFileWithCheck(channelScemaFile,etree.parse)
        if not self.isReady:
            logger.critical(ERROR['GENERAL']['MISSING_TO_START'])
            return
        
        self.userGroups = self.getValueFromKH('userGroups')
        self.exercisesPath = self.getValueFromKH(EXERCISE_PATH)
        self.schemaParser = etree.XMLParser(schema = etree.XMLSchema(self.schema))
        if chSchema is not None:
            self.chSchemaParser = etree.XMLParser(schema = etree.XMLSchema(chSchema))        
        # Load all exercise from given directory
        self.exerciseRoots = None
        self.reloadAllExercises()


    def isReady(self):
        return self.globalConf and self.schema

    def createResultContent(self,exerciseID,ownerID, logger, runningID, command):
        return resultContent(exerciseID,ownerID,self.exerciseRoots,self.getValueFromKH,self.getUserFromUserGroups,self.giveBackUser,logger,runningID,command)    

    def getValueFromKH(self,key, commandDict=None,exerciseRoot=None):
        result = None
        if commandDict is not None and key in commandDict:
            result = commandDict[key]
        elif exerciseRoot is not None:
            exerciseDict = collections.defaultdict(list)
            exerciseKeysNode = exerciseRoot.find('.//'+EXERCISE_VARIABLES)
            if exerciseKeysNode is not None:
                for exerciseKey in exerciseKeysNode:
                    if exerciseKey.get('key') is not None:
                        exerciseDict[exerciseKey.get('key')].append(exerciseKey.text)
            if key in exerciseDict:
                result = exerciseDict[key][0] if len(exerciseDict[key]) == 1 else exerciseDict[key]
        
        if result is None:
            if self.localConf is not None and key in self.localConf:
                result = self.localConf[key]
            elif key in self.globalConf:
                result = self.globalConf[key]  
            else:
                raise AKEPException(ERROR['NOT_FIND']['KEY_IN_HIERAR']+key)
        
        # if the value start with @ character, put to eval function
        if isinstance(result,str) and result != '' and result[0]=='@':
            result = str(eval(result[1:]))
        if commandDict is not None:
            commandDict[key] = result
        
        return result

    def checkExerciseValid(self,source):
        try:
            return etree.parse(source, self.schemaParser)
        except:
            raise

    def checkTaskChannelInputStreamValid(self,source):
        try:
            return etree.parse(source,self.chSchemaParser)
        except:
            raise

    def checkTaskChannelStringValid(self,text):
        try:
            return etree.fromstring(text, self.chSchemaParser)
        except:
            raise

    def reloadAllExercises(self):
        if self.exerciseRoots is None:
            self.exerciseRoots = {}
        for path in iglob(self.exercisesPath + '/' + EXERCISE_FILE_FORMAT):
            elementTreeObject = self.openFileWithCheck(path,self.checkExerciseValid)
            if elementTreeObject is not None:
                key = path.rsplit('.', 2)[1]
                self.exerciseRoots[key] = elementTreeObject.getroot()
                self.logger.info('Exercise loaded: '+key)


    def openFileWithCheck(self,path,loader=None):
        if os.path.isfile(path):        
            try:
                data = open(path)
            except IOError:
                self.logger.exception(ERROR['GENERAL']['PERMISSON']+' read of file: '+path)
            else:
                try:
                    return loader(data) if callable(loader) else data
                except:
                    self.logger.exception(ERROR['FILE']['INVALID']+path)
        else:
            self.logger.warning(ERROR['FILE']['NOT_FIND']+path)
        return None

    def getUserFromUserGroups(self,group):
        if group in self.userGroups:
            self.lock.acquire()
            if len(self.userGroups[group]) != 0:                
                userObject = self.userGroups[group][0]
                self.userGroups[group].remove(userObject)
                self.lock.release()
                return userObject
            else:
                self.lock.release()
                raise AKEPException('No available user in group: '+group)
        else:
            raise AKEPException(ERROR['NOT_FIND']['USER_GROUP'].format(group))
        

    def giveBackUser(self,group,userObject):
        self.userGroups[group].append(userObject)