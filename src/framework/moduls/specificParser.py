import re
from lxml import etree
from moduls.exceptions import *
import uuid


class SQLTaskParser:
    @staticmethod
    def getXMLToOutput(text, checkChSintaxFn, logger, parserConfig):
        replaceToEmpty = ['set feedback (on|off)', '(?!--#)--.*', 'prompt']
        for replaceItem in replaceToEmpty:
            text = re.sub(replaceItem, '', text)
        xmlContent = text[text.find('<tasks>'):text.find('</tasks>') + 8]
        # logger.debug(xmlContent)
        try:
            xmlContent = etree.fromstring(xmlContent, parser=etree.XMLParser(encoding='utf8', huge_tree=True))
        except Exception as err:
            raise AKEPException('Not well formed xml from channel, details: {}'.format(str(err)))

        return checkChSintaxFn(etree.tostring(xmlContent, encoding='utf8'))

    @staticmethod
    def getTextToInput(text, checkChSintaxFn, insertTasksList, logger, parserConfig):
        SQLTaskParser.getXMLToOutput(text, checkChSintaxFn, logger, parserConfig)
        tasksStartIndex = text.find('prompt <tasks>')
        if tasksStartIndex == -1:
            raise AKEPException('Not well formed task schema, details: {}'.format('not found open tasks element'))
        preText = text[0:tasksStartIndex]
        tasksStopIndex = text.find('</tasks>')
        if tasksStopIndex == -1:
            raise AKEPException('Not well formed task schema, details: {}'.format('not found close tasks element'))
        postText = text[tasksStopIndex + 8:]
        relevantText = text[tasksStartIndex:tasksStopIndex + 8]
        # logger.debug(relevantText)
        findStartIndex = 0
        while True:
            findStartIndex = relevantText.find('<tasks>' if findStartIndex == 0 else '</task>', findStartIndex)
            if findStartIndex == -1:
                break
            findStartIndex += 7
            findStopIndex = relevantText.find('prompt <task', findStartIndex)
            if findStopIndex == -1:
                break

            result = re.search('<task n=\"(?P<n>.+)\">', relevantText[findStopIndex:])
            text = relevantText[findStartIndex:findStopIndex]
            nAttrR = result.group('n').split('.')

            if len(nAttrR) == 0:
                nAttr = str(int(nAttrR[0]) - 1)
            else:
                nAttr = '.'.join(nAttrR[:-1]) + '.' + str(int(nAttrR[len(nAttrR) - 1]) - 1)
            nAttr += '.~'

            insertText = SQLTaskParser._getTaskElement(text, nAttr)
            relevantText = relevantText[:findStartIndex] + insertText + relevantText[findStopIndex:]
            findStartIndex += len(insertText)
        relevantText = relevantText.replace('prompt', '')
        # logger.debug(relevantText)
        xmlContent = checkChSintaxFn(relevantText)

        for task in insertTasksList:
            newTask = etree.Element('task', {'n': task['taskID']})
            newTask.text = etree.CDATA(task['input'])
            xmlContent.append(newTask)

        if parserConfig is not None and len(parserConfig.xpath('order')):
            result = ''
            orderList = [item.strip() for item in parserConfig.xpath('order')[0].text.split(';')]
            for orderItem in orderList:
                findElement = xmlContent.xpath('//task[@n="{}"]'.format(orderItem))
                findElementCustom = parserConfig.xpath('//customInput[@name="{}"]'.format(orderItem))
                if len(findElementCustom):
                    result += SQLTaskParser._getTaskElement(findElementCustom[0].text, uuid.uuid4())
                elif len(findElement):
                    result += SQLTaskParser._getTaskElement(findElement[0].text, orderItem)
                else:
                    logger.warning('Not found reference to task {}'.format(orderItem))

            return preText + '<tasks>' + result + '</tasks>' + postText

        xslt_tree = etree.XML('''
        <xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="2.0">
            <xsl:output encoding="utf8" method="text"/>
            <xsl:template match="tasks">
                <![CDATA[prompt <tasks>]]>
                    <xsl:apply-templates select="task">
                        <xsl:sort select="@n" />
                    </xsl:apply-templates>
                <![CDATA[prompt </tasks>]]>
            </xsl:template>
            <xsl:template match="task">
                <![CDATA[prompt <task n="]]><xsl:value-of select="@n"/><![CDATA[">]]>
                <![CDATA[prompt <![CDATA[]]>
                <xsl:apply-templates/>
                <![CDATA[prompt ]]]]><![CDATA[>]]>
                <![CDATA[prompt </task>]]>
                </xsl:template>
        </xsl:stylesheet>
        ''')
        transform = etree.XSLT(xslt_tree)

        return preText + str(transform(xmlContent)) + postText

    @staticmethod
    def _getTaskElement(text, nAtt):
        return '''
        prompt <task n="{}">
        prompt <![CDATA[
        {}
        prompt ]]>
        prompt </task>
        '''.format(nAtt, text)
