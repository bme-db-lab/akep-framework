from moduls.schemaSpecificAttr import *
from moduls.exceptions import *
from moduls.resultContent import resultContent
import os
from lxml import etree
from lxml import html
import json
import collections
import threading

# moduls to use eval
import time
import queue


class dataStore:
    def __init__(self, localConfigFile, schemaFile, logger, channelScemaFile=None):
        self.logger = logger
        self.globalConf = self.openFileWithCheck(
            os.path.dirname(os.path.realpath(__file__)) + "/../" + GLOBAL_CONF_FILE, json.load)
        self.localConf = self.openFileWithCheck(localConfigFile, json.load)
        self.schema = self.openFileWithCheck(schemaFile, etree.parse)
        chSchema = None if channelScemaFile is None else self.openFileWithCheck(channelScemaFile, etree.parse)
        if not self.isReady:
            logger.critical(ERROR['GENERAL']['MISSING_TO_START'])
            return

        userGroups = self.getValueFromKH('userGroups')

        self.userPool = {}

        for userType, users in userGroups.items():
            self.userPool[userType] = queue.Queue()
            for user in users:
                self.userPool[userType].put(user)

        self.schemaParser = etree.XMLParser(schema=etree.XMLSchema(self.schema))
        if chSchema is not None:
            self.chSchemaParser = etree.XMLParser(schema=etree.XMLSchema(chSchema))

    def isReady(self):
        return self.globalConf and self.schema

    def createResultContent(self, exerciseID, ownerID, logger, runningID, command, exerciseRoots):
        return resultContent(exerciseID, ownerID, exerciseRoots, self.getValueFromKH, self.getUserFromUserGroups,
                             self.giveBackUser, logger, runningID, command)

    def getValueFromKH(self, key, commandDict=None, exerciseRoot=None):
        """
        The key hierarhy function
        Order to find a key's value: command, exerciseRoot, local config, global config
        """
        result = None
        if commandDict is not None and key in commandDict:
            result = commandDict[key]
        elif exerciseRoot is not None:
            exerciseDict = collections.defaultdict(list)
            exerciseKeysNode = exerciseRoot.xpath('.//' + EXERCISE_VARIABLES+'/Key')
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
                raise AKEPException(ERROR['NOT_FOUND']['KEY_IN_HIERAR'] + key)

        # if the value start with @ character, put to eval function
        if isinstance(result, str) and result != '' and result[0] == '@':
            try:
                result = str(eval(result[1:]))
            except:
                logger.warning('Not valid eval value')
                pass

        if commandDict is not None:
            # save the result so it can be load from command later
            commandDict[key] = result

        return result

    def checkExerciseValid(self, source):
        try:
            return etree.parse(source, self.schemaParser)
        except:
            raise

    def checkTaskChannelInputStreamValid(self, source):
        try:
            return etree.parse(source, self.chSchemaParser)
        except:
            raise

    def checkTaskChannelStringValid(self, text):
        try:
            return etree.fromstring(text, self.chSchemaParser)
        except:
            raise

    def stringToXMLTree(text):
        try:
            return etree.fromstring(text)
        except Exception as error:
            return etree.fromstring('<error><![CDATA['+str(error)+']]></error>')

    def stringToHTMLTree(text):
        try:
            return html.fromstring(text)
        except Exception as error:
            return etree.fromstring('<error><![CDATA[' + str(error) + ']]></error>')

    def openFileWithCheck(self, path, loader=None):
        """
        Open a file and check with loader the schema if loader is not None
        return the loader(data) reference if loader is not None else just file data
        """
        if os.path.isfile(path):
            try:
                data = open(path)
            except IOError:
                self.logger.exception(ERROR['GENERAL']['PERMISSON'] + ' read of file: ' + path)
            else:
                try:
                    return loader(data) if callable(loader) else data
                except:
                    self.logger.exception(ERROR['FILE']['INVALID'] + path)
        else:
            self.logger.warning(ERROR['FILE']['NOT_FOUND'] + path)
        return None

    def getUserFromUserGroups(self, group):
        """
        User pool defined by value of userGroups key
        return a user (a user object from userGroups), or AKEPException if no available user
        """

        return self.userPool[group].get()

    def giveBackUser(self, group, userObject):
        """
        Give back the user to the pool
        """
        self.userPool[group].task_done()
        self.userPool[group].put(userObject)
        # self.userGroups[group].append(userObject)
