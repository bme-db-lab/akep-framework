from moduls.schemaSpecificAttr import *

import os
import threading

class analyse:
    lock = threading.Lock()

    def __init__(self,genAnalyseObj,akepProcAnalyseOb,targetFolder):
        self.genAnalyseObj = genAnalyseObj
        self.akepProcAnalyseOb = akepProcAnalyseOb
        self.targetFolder = targetFolder

    def __makePropData(self,anType):
        result = []
        if anType == 'chAnalyse':
            result.append(','.join(ANALYSE_CH_PROP))            
        elif anType == 'solAnalyse':
            result.append(','.join(ANALYSE_EVAL_PROP))
        else:
            result.append(','.join(ANALYSE_TASK_PROP))
        
        if self.akepProcAnalyseOb[anType] is None:
            return result
        for row in self.akepProcAnalyseOb[anType]:
            result.append(','.join(row))
        return result
    
    def __makeAssesmentRunData(self):
        result = []
        result.append(','.join(ANALYSE_ASSESMENT_RUN))
        toResult = []
        for key in ANALYSE_ASSESMENT_RUN:
            toResult.append(str(self.genAnalyseObj[key]))
        result.append(','.join(toResult))
        return result

    def run(self):
        chPropData = self.__makePropData('chAnalyse')
        evPropData = self.__makePropData('solAnalyse')
        taskPropData = self.__makePropData('taskAnalyse')
        aRunData = self.__makeAssesmentRunData()

        self.lock.acquire()
        if not os.path.exists(self.targetFolder+'/'+self.genAnalyseObj['exID']):
            os.makedirs(self.targetFolder+'/'+self.genAnalyseObj['exID'])

        if os.path.exists(self.targetFolder+'/assesmentRun.data'):
            del aRunData[0]

        with open(self.targetFolder+'/assesmentRun.data','a') as f:
            f.write('\n'.join(aRunData)+'\n')
        self.lock.release()

        target = self.targetFolder+'/'+self.genAnalyseObj['exID']+'/'+self.genAnalyseObj['FolderID']
        os.makedirs(target)
        with open(target + '/channel_prop.data','w') as f:
            f.write('\n'.join(chPropData))
        with open(target + '/evaluate_prop.data','w') as f:
            f.write('\n'.join(evPropData))
        with open(target + '/task_prop.data','w') as f:
            f.write('\n'.join(taskPropData))

