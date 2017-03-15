from moduls.schemaSpecificAttr import *
from moduls.exceptions import *
from lxml import etree
import copy
import re


class resultContent:
    def __init__(self, exerciseID, ownerID, exerciseRoots, keyFn, getUserFn, giveBackUserFn, logger, runningID,
                 command):
        if exerciseID not in exerciseRoots:
            raise AKEPException(ERROR['NOT_FOUND']['EXERCISE_TO_ID'] + exerciseID)
        self.resultXMLRoot = copy.deepcopy(exerciseRoots[exerciseID])
        self.resultXMLRoot.set(EXERCISE_ID, exerciseID)
        self.resultXMLRoot.set(OWNER_ID, ownerID)
        self.resultXMLRoot.set(OWNER_ID, ownerID)
        self.resultXMLRoot.set('timeStamp', keyFn('timeStamp', command))
        self.keyFn = keyFn
        self.getUserFn = getUserFn
        self.exerciseRoots = exerciseRoots
        self.logger = logger
        self.runningID = runningID
        self.giveBackUserFn = giveBackUserFn
        self.command = command

    def deleteNotOutTags(self):
        """
        Filter all elements which are has tagname from value of RESULT_NOT_COPY key and all element which has NOT_COPY_TO_RESULT_ATTR attr
        """
        for node in self.getAll(attrName=NOT_COPY_TO_RESULT_ATTR, attrValue='false'):
            parent = node.getparent()
            parent.remove(node)

        notCopyTags = self.keyFn(RESULT_NOT_COPY, self.command, self.resultXMLRoot)
        for tagName in notCopyTags:
            for node in self.getAll(tag=tagName):
                parent = node.getparent()
                parent.remove(node)

    def referenceFormating(self):
        self.referenceProcessor(self.resultXMLRoot, self.resultXMLRoot.get(REFERENCE_EXERCISE),
                                self.resultXMLRoot.get(REFERENCE_ID), self.resultXMLRoot.get(REF_CHILDREN_FIND))
        for element in self.getAll(attrName=REFERENCE_EXERCISE):
            self.referenceProcessor(element, element.get(REFERENCE_EXERCISE), element.get(REFERENCE_ID),
                                    element.get(REF_CHILDREN_FIND))

    def referenceProcessor(self, element, referenceExercise, referenceWithinExercise=None, referenceChildrenFind=None):
        """
        Push referenced element as a element's child or replace the placeholder element
        """
        if referenceExercise is None:
            return
        if referenceExercise not in self.exerciseRoots:
            raise AKEPException(ERROR['NOT_FOUND']['EXERCISE_TO_ID'] + referenceExercise)
        remoteElement = self.getAll(attrName=REFERENCE_TARGET_ID, attrValue=referenceWithinExercise,
                                    element=self.exerciseRoots[
                                        referenceExercise]) if referenceWithinExercise is not None else \
            self.exerciseRoots[referenceExercise]
        if remoteElement is None:
            element.set(TO_ELEMENT_ERROR_ATTR, 'ReferenceError')
            return

        elementParent = None
        if element.get('refPlaceholder') is not None:
            elementParent = element.getparent()
            elementStartInd = elementParent.index(element)
            elementParent.remove(element)

        for ind, child in enumerate(
                remoteElement if referenceChildrenFind is None else self.getAll(findText=referenceChildrenFind,
                                                                                element=remoteElement)):
            if elementParent is None:
                # copy as element's child
                element.append(copy.deepcopy(child))
            else:
                # copy to placeholder position + ind
                elementParent.insert(elementStartInd + ind, copy.deepcopy(child))

    def keyBinding(self, element=None):
        """
        Replace all $key$ with key's value
        runningID, username, password are built in keys
        """
        elementText = etree.tostring(self.resultXMLRoot if element is None else element).decode('utf-8')
        for key in re.findall(BINDING_REGEX, elementText):
            self.logger.debug('find key: ' + key)
            if key == 'runningID':
                value = self.runningID
            elif key == 'username' or key == 'password':
                if not hasattr(self, 'user'):
                    self.usergroup = self.keyFn('runUserGroup', self.command, self.resultXMLRoot)
                    self.user = self.getUserFn(self.usergroup)
                value = self.user[key]
            else:
                value = self.keyFn(key, self.command, self.resultXMLRoot)
            self.logger.debug('value: ' + value)
            elementText = elementText.replace('$' + key + '$', value)

        if element is not None:
            return etree.fromstring(elementText)
        self.resultXMLRoot = etree.fromstring(elementText)

    ###### Helper functions #######

    def getScripts(self):
        scripts = []
        for script in self.getAll(tag='script'):
            scriptItem = dict(script.attrib.items())
            scriptItem['node'] = script
            scripts.append(scriptItem)
        return scripts

    def getAll(self, tag=None, attrName=None, attrValue=None, element=None, findText=None, direct=False):
        element = self.resultXMLRoot if element is None else element
        per = './/' if not direct else './'
        if findText is not None:
            return element.findall(findText)
        if attrValue is not None and attrName is not None:
            return element.findall(
                per + tag + '[@' + attrName + '="' + attrValue + '"]') if tag is not None else element.findall(
                per + '*[@' + attrName + '="' + attrValue + '"]')
        if attrName is not None:
            return element.findall(per + tag + '[@' + attrName + ']') if tag is not None else element.findall(
                per + '*[@' + attrName + ']')
        if tag is not None:
            return element.findall(per + tag)
        return []

    def get(self, tag=None, attrName=None, attrValue=None, element=None, findText=None, direct=False):
        result = self.getAll(tag, attrName, attrValue, element, findText, direct)
        return None if len(result) == 0 else result[0]

    def giveBackUser(self):
        if hasattr(self, 'user'):
            self.giveBackUserFn(self.usergroup, self.user)

    def setAttr(tag, attrName, value):
        tag.set(attrName, value)

    def getAttrValue(tag, attrName):
        return tag.get(attrName)

    def createElement(elementName, attrDict=None):
        return etree.Element(elementName, attrDict)

    def appendTo(element, parent):
        parent.append(element)

    def getText(element):
        return element.text

    def setText(element, text):
        element.text = text

    def toStringFromElement(element):
        return etree.tostring(element, encoding="utf8")

    def toString(self):
        return etree.tostring(self.resultXMLRoot, encoding="utf8")

    def getChildren(element):
        return element.getchildren()

    def getParent(element):
        return element.getparent()

    def isElementType(element):
        return isinstance(element, etree._Element)
