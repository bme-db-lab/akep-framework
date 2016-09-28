from moduls.schemaSpecificAttr import *
from moduls.exceptions import *
from moduls.resultContent import resultContent
import os
from lxml import etree
import json
from glob import iglob
import collections

class dataStore:
    def __init__(self, localConfigFile, schemaFile, logger, channelScemaFile = None):
        self.logger = logger
        self.globalConf = self.__openFileWithCheck(os.path.dirname(os.path.realpath(__file__))+"/../"+GLOBAL_CONF_FILE,json.load)
        self.localConf = self.__openFileWithCheck(localConfigFile,json.load)
        self.schema = self.__openFileWithCheck(schemaFile,etree.parse)
        chSchema = None if channelScemaFile is None else self.__openFileWithCheck(channelScemaFile,etree.parse)
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
        if commandDict is not None and key in commandDict:
            return commandDict[key]
        if exerciseRoot is not None:
            exerciseDict = collections.defaultdict(list)
            exerciseKeysNode = exerciseRoot.find('.//'+EXERCISE_VARIABLES)
            if exerciseKeysNode is not None:
                for exerciseKey in exerciseKeysNode:
                    if exerciseKey.get('key') is not None:
                        exerciseDict[exerciseKey.get('key')].append(exerciseKey.text)
            if key in exerciseDict:
                return exerciseDict[key][0] if len(exerciseDict[key]) == 1 else exerciseDict[key]
        if self.localConf is not None and key in self.localConf:
            return self.localConf[key]
        if key in self.globalConf:
            return self.globalConf[key]
        raise AKEPException(ERROR['NOT_FIND']['KEY_IN_HIERAR']+key)

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
            elementTreeObject = self.__openFileWithCheck(path,self.checkExerciseValid)
            if elementTreeObject is not None:
                key = path.rsplit('.', 2)[1]
                self.exerciseRoots[key] = elementTreeObject.getroot()
                self.logger.info('Exercise loaded: '+key)


    def __openFileWithCheck(self,path,loader=None):
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
            if len(self.userGroups[group]) != 0:
                userObject = self.userGroups[group][0]
                self.userGroups[group].remove(userObject)
                return userObject
            else:
                raise AKEPException('No available user in group: '+group)
        else:
            raise AKEPException('No find user group: '+group)
        

    def giveBackUser(self,group,userObject):
        self.userGroups[group].append(userObject)