#!/usr/bin/python3
import subprocess
import xml.etree.ElementTree as ET
import evaluateMode
import queue
import threading
import socket
import os
import re
import time
import datetime
import argparse
import sys

from util.xmlHelper import *

parser = argparse.ArgumentParser('AKÉP')
parser.add_argument('-p','--port', metavar='port', help='Server listener portnumber', default=5555, type=int)
parser.add_argument('-E','--Epath',metavar='path', help='Relative exercise XMLs path', default='.', type=str)
parser.add_argument('-L','--tooLong',metavar='tooLong', help='If output tooLong AKEP will cut it', default=2000, type=int)
parser.add_argument("-a","--allnetwork", help="Listening on all interface", action='store_true')
args = parser.parse_args()

workDir = os.path.dirname(os.path.realpath(__file__)) + '/' + args.Epath if args.Epath[0] != '/' else args.Epath

if workDir[len(workDir) - 1] == '/':
	workDir = workDir[:-1]

print('WorkDir: '+workDir)

print('Listen: '+('all interface' if args.allnetwork else 'localhost') + ' on port:'+str(args.port))

#configure

workQueue = queue.Queue(100)
threadNumber = 20
exerciseRoots = [None] * 100
exerciseRootsModifiedTime = [None] * 50
runEvulatorUser = [True] * 20

#define thread work variable
exitFlag = False
threads = []
queueLock = threading.Lock()


'''If socket get a process message it convert to Process object'''
class Process:
	__labNumber = ''
	__exerciseNumber = 0
	__timeout = False
	__resultXMLRoot = None
	__socket = None
	__user = -1
	__channelRoots = {}
	__replace = {}

	error = False

	'''Create inputs to preprocessor and initialize result XML root'''
	def __init__(self,socket, exerciseNumber, labNumber,schema,sol):
		self.__socket = socket
		self.__labNumber = labNumber
		self.__exerciseNumber = exerciseNumber

		self.__replace['schema'] = schema
		self.__replace['passw'] = 'PASSWORD_REPLACE_ME'
		self.__replace['workdir'] = workDir
		self.__replace['sol'] = sol
		self.__replace['eid'] = str(exerciseNumber)

		print('User: '+schema + ' Lab: '+str(labNumber) + ' ExNu: '+str(exerciseNumber))

		if exerciseRoots[exerciseNumber] is None:
			print('No exist exercise.N.xml')
			self.error = True
			return

		if exerciseRoots[exerciseNumber].find('./exercise[@n="'+labNumber+'"]') is None:
			print('No exist exercise')
			self.error = True
			return

		user = ''
		if labNumber == '1':
			user = 'ertekelo'
		else:
			if args.allnetwork:
				for i in range(0, 19):
					if runEvulatorUser[i]:
						runEvulatorUser[i] = False
						self.__user = i
						user = 'DB_USERNAME_REPLACE_ME_0'+str(i) if i < 10 else 'DB_USERNAME_REPLACE_ME_'+str(i)
						break
			if user == '':
				user = 'DB_USERNAME_REPLACE_ME'

		self.__replace['user'] = user

		self.__channelRoots['Main'] = self.script(exerciseRoots[exerciseNumber].find('./exercise[@n="'+labNumber+'"]'))
		for scriptInit in exerciseRoots[exerciseNumber].findall('./exercise[@n="'+labNumber+'"]/script'):
			self.__channelRoots[scriptInit.get('channelName')] = self.script(scriptInit)

		#Output result XML to the socket caller
		self.__resultXMLRoot = ET.Element('exercise',{'EID':str(exerciseNumber),'LID':str(labNumber), 'User':schema})

	def getSocket(self):
		return self.__socket

	def script(self,target):
		channelRoot = {}
		channelRoot['channelFormat'] = target.get('channelFormat') if target.get('channelFormat') is not None else 'xml'
		channelRoot['Path'] = self.replaceIDs(target.get('scriptPath'))
		channelRoot['ParameterString'] = self.replaceIDs(target.get('arguments'))
		channelRoot['Entry'] = target.get('entry')
		channelRoot['InputStream'] = []

		for input in target.findall('./inputstream'):
			channelRoot['InputStream'].append({'fromXML':False,'text':self.replaceIDs(input.text)} if input.get('fromXML') is None else {'fromXML':True,'text':self.replaceIDs(input.get('fromXML'))})

		return channelRoot

	def replaceIDs(self, param):
		for key in self.__replace:
			if self.__replace[key] is not None:
				param = param.replace('$'+key,self.__replace[key])
		return param

	def userpool(self):
		with queueLock:
			if self.__user != -1:
				runEvulatorUser[self.__user] = True

	def generateInputStreamFromXML(self, XMLPath, channelName):
		try:
			xmlRoot = ET.fromstring(open(XMLPath, 'r').read())
			result = 'print|||<tasks>\n'
			for task in xmlRoot.findall('.//task'):
				result += 'print|||<task n="'+task.get('n')+'">\n'
				if len(task.findall('./subtask')) == 0:
					result += 'print|||<![CDATA[\n'
					result += re.sub('^\s+','',task.text) + '\n'
					result += 'print|||]]>\n'
				else:
					for subtask in task.findall('./subtask'):
						result += 'print|||<subtask n="'+subtask.get('n')+'">\n'
						result += 'print|||<![CDATA[\n'
						result += re.sub('\s+$','',re.sub('^\s+','',subtask.text)) + '\n'
						result += 'print|||]]>\n'
						result += 'print|||</subtask>\n'
				result += 'print|||</task>\n'
			result += 'print|||</tasks>'
			return result
		except:
			self.error = True
			print(channelName + ' => [Script inputStream error]')
			return None


	def runSubProcess(self,channelName):
		print('[Wait '+self.__channelRoots[channelName]['Path']+' script ...]')
		inputStream = ''
		for input in self.__channelRoots[channelName]['InputStream']:
			if input['fromXML']:
				inputFromXML = self.generateInputStreamFromXML(input['text'], channelName)
				if inputFromXML is None:
					return
				inputStream += inputFromXML + '\n'
			else:
				inputStream += input['text'] + '\n'

		arguments = [self.__channelRoots[channelName]['ParameterString']] if len(self.__channelRoots[channelName]['ParameterString'].split('=')) == 0 else self.__channelRoots[channelName]['ParameterString'].split('=')
		scall = [self.__channelRoots[channelName]['Path']]
		for arg in arguments:
			for argi in arg.split(' '):
				scall.append(argi)
		#print(scall)
		with subprocess.Popen(scall, stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=subprocess.PIPE, universal_newlines=True) as proc:
			try:
				self.__channelRoots[channelName]['out'], self.__channelRoots[channelName]['error'] = proc.communicate(input=inputStream,timeout=60)
			except subprocess.TimeoutExpired:
				self.__timeout = True
				print(channelName + ' =>  [Script timeout]')
				proc.kill()
				return


		print(channelName + ' =>  [Script run finish]')

		if self.__channelRoots[channelName]['channelFormat'] == 'xml':
			self.__channelRoots[channelName]['out'] = self.__channelRoots[channelName]['out'][self.__channelRoots[channelName]['out'].find('<tasks>'):self.__channelRoots[channelName]['out'].find('</tasks>')+8]
			#print(self.__channelRoots[channelName]['out'])
			try:
				self.__channelRoots[channelName]['out'] = ET.fromstring(self.__channelRoots[channelName]['out'])
			except:
				self.error = True
				with queueLock:
					self.__socket.send(b'script output parse error')
					print('script output parse error')
					print(sys.exc_info()[1])
					self.__socket.shutdown(socket.SHUT_RDWR)
				return

	'''Run the given script with given arguments and inputstream'''
	def run(self, threadName):
		print(str(self.__user)+':'+self.__replace['schema']+'-'+str(self.__exerciseNumber)+': '+threadName)
		#run preScripts
		for key in self.__channelRoots:
			if (self.__channelRoots[key]['Entry'] == 'pre'):
				self.runSubProcess(key)
				if self.error:
					return

		self.runSubProcess('Main')
		if self.error:
			return

		for key in self.__channelRoots:
			if (self.__channelRoots[key]['Entry'] == 'post'):
				self.runSubProcess(key)
				if self.error:
					return

	'''Get task output from rootObject (source or preprocessor output channel)'''
	def getExerciseTask(self,task, rootObject):
		if task.tag == 'subtask':
			result = rootObject.find('.//subtask[@n="'+task.get('n')+'"]')
		else:
			result = rootObject.find('.//task[@n="'+task.get('n')+'"]')

		return result.text if result is not None else ''


	'''Get task content from channel. channel is passed as a ChannelType enum member. Whitespaces are removed from contents beginning and end (trimmed).'''
	def getChannelContent(self, channel, task, toLowerCase=True):
		output = ''
		if channel is None:
			output = self.getExerciseTask(task, self.__channelRoots['Main']['out'])
		else:
			if channel not in self.__channelRoots:
				return None
			if self.__channelRoots[channel]['channelFormat'] == 'xml':
				output = self.getExerciseTask(task, self.__channelRoots[channel]['out'])
			else:
				output = self.__channelRoots[channel]['out']

		if output is None:
			output = ''

		#reformed result
		output = re.sub('(^\s+|\s+$)','',output)
		if toLowerCase:
			output = output.lower()

		return output

	'''Run the given task solutions with specific evaluateMode functions'''
	def runEvaluateRutin(self,task,sol,solItem, result, bonus, resultTask):
		#get result from specified channel
		output = self.getChannelContent(solItem.get('channelName'),task)

		ETappendChildTruncating(resultTask, 'Output' if solItem.get('channelName') is None else solItem.get('channelName'), output, args.tooLong)

		if task.find('solution') is None:
			ET.SubElement(resultTask,'Required').text = re.sub('\s+$','',re.sub('^\s+','',task.find('description').text if task.find('description') is not None else ''))
			return


		if output != '':
			#remove white space characters from exercises.N.xml specified sol. element text
			solution = re.sub('\s+',' ',solItem.text).strip(' ').lower()

			ET.SubElement(resultTask,'Required').text = solution

			with queueLock:
				#get the result from evaluateMode and score it with solution score
				try:
					res = getattr(evaluateMode, solItem.get('evaluateMode'))(output,solution,solItem.get('evaluateArgs'))
				except:
					print('Error in evaluateMode: ' + solItem.get('evaluateMode') + ' Task: '+task.get('n'))
					return [result,bonus]

				val = float(sol.get('score')) if (solItem.get('negation')==None and res) or (solItem.get('negation') and not res) else 0

			#val add to bonusScore or resultScore depends by bonus attribute
			if sol.get('bonus') is not None and val > bonus:
				bonus = val
			elif sol.get('bonus') is None and val > result:
				result = val
		return [result,bonus]

	'''Calc the score'''
	def evaluate(self,task,resultTask):
		result = [0,0]
		#if manual test
		if task.find('solution') is None:
			self.runEvaluateRutin(task,None,task, 0, 0, resultTask)
			return result
		#if automatic test
		#solutionItems connect together with AND logic
		#solutions connect together with OR logic
		for sol in task.findall('solution'):
			if len(sol.findall('solutionItem')) == 0:
				resultSol = ET.SubElement(resultTask,'Solution',{'method':sol.get('evaluateMode')})
				result = self.runEvaluateRutin(task,sol,sol, result[0], result[1], resultSol)
				resultSol.set('result',str(result))
			else:
				oldresult = result[0]
				notBreak = True
				resultSol = ET.SubElement(resultTask,'Solution')
				for solItem in sol.findall('solutionItem'):
					result[0] = 0
					resultSubSol = ET.SubElement(resultSol,'SubSolution',{'method':solItem.get('evaluateMode')})
					result = self.runEvaluateRutin(task,sol,solItem, result[0], result[1], resultSubSol)
					resultSubSol.set('result',str(result))
					if result[0] == 0:
						notBreak = False
				# if a single solutionItem scored for 0 points, this solution gets 0 points.
				if not notBreak:
					result[0] = 0
				# if the current solution scores less than the previous, then retain the previous score
				if result[0] < oldresult:
					result[0] = oldresult

		return [result[0] + result[1], float(task.findall('solution')[0].get('score'))]



	'''Create result output with call evaluate function to every task, listen to reference'''
	def evaluateAll(self):
		if self.__timeout:
			with queueLock:
				self.__resultXMLRoot.set('TimeOut','True')
				self.__socket.send(ET.tostring(self.__resultXMLRoot))
				self.__socket.shutdown(socket.SHUT_RDWR)
			return

		scoreResult = 0
		scoreMax = 0
		resultTasks = ET.SubElement(self.__resultXMLRoot,'taskDetails')
		exercise = exerciseRoots[self.__exerciseNumber].find('./exercise[@n="'+self.__labNumber+'"]')
		actExercise = exercise if exercise.get('reference') is None else exerciseRoots[int(exercise.get('reference'))].find('./exercise[@n="'+self.__labNumber+'"]')

		prevgroupTaskNode = None
		groupResultTask = None
		groupScore = [0,0]
		taskScore = [0,0]
		tasks = actExercise.findall('.//task')
		actindex = 1

		for task in tasks:
			groupTaskNode = exerciseRoots[self.__exerciseNumber].find('./exercise[@n="'+self.__labNumber+'"]//task[@n="'+task.get('n')+'"]/..')
			if groupTaskNode is not None and groupTaskNode.tag != 'taskgroup':
				groupTaskNode = None
			if task.get('reference') is not None:
				for child in exerciseRoots[int(task.get('reference'))].find('./exercise[@n="'+self.__labNumber+'"]//task[@id="'+task.get('reference-id')+'"]'):
					task.append(child)

			if groupTaskNode is None:
				resultTask = ET.SubElement(resultTasks,'Task',{'n':task.get('n')})
				if groupResultTask is not None:
					groupResultTask.set('Score',str(groupScore[0])+'/'+str(groupScore[1]))
					groupScore = [0,0]
					prevgroupTaskNode = None
			elif prevgroupTaskNode != groupTaskNode:
				if groupResultTask is not None:
					groupResultTask.set('Score',str(groupScore[0])+'/'+str(groupScore[1]))
				prevgroupTaskNode = groupTaskNode
				groupResultTask = ET.SubElement(resultTasks,'TaskGroup',{'title':groupTaskNode.get('title')})
				resultTask = ET.SubElement(groupResultTask,'Task',{'n':task.get('n')})
				groupScore = [0,0]
			else:
				resultTask = ET.SubElement(groupResultTask,'Task',{'n':task.get('n')})

			TaskText = ET.SubElement(resultTask,'TaskText')
			TaskText.text = task.find('./tasktext').text if task.find('./tasktext') is not None else ''

			if len(task.findall('./subtask')) == 0:
				Description = ET.SubElement(resultTask,'Description')
				Description.text = task.find('./description').text if task.find('./description') is not None else ' '
				# add source code here
				output = self.getChannelContent('Source', task, False)
				ETappendChildTruncating(resultTask, 'Source', output, args.tooLong)
				# go on to scoring
				actScore = self.evaluate(task,resultTask)
				taskScore[0] = actScore[1]
				taskScore[1] = actScore[0]
				scoreResult += actScore[0]
				scoreMax += actScore[1]
			else:
				for subtask in task.findall('./subtask'):
					resultSubTask = ET.SubElement(resultTask,'SubTask',{'n':subtask.get('n')})
					Description = ET.SubElement(resultSubTask,'Description')
					Description.text = subtask.find('./description').text if subtask.find('./description') is not None else ''
					TaskText = ET.SubElement(resultSubTask,'TaskText')
					TaskText.text = subtask.find('./tasktext').text if subtask.find('./tasktext') is not None else ''
					# add source code here
					output = self.getChannelContent('Source', subtask, False)
					ETappendChildTruncating(resultSubTask, 'Source', output, args.tooLong)
					# go on to scoring
					actScore = self.evaluate(subtask,resultSubTask)
					resultSubTask.set('Score',str(actScore[1])+'/'+str(actScore[0]))
					taskScore[0] += actScore[1]
					taskScore[1] += actScore[0]
					scoreResult += actScore[0]
					scoreMax += actScore[1]

			resultTask.set('Score',str(taskScore[0])+'/'+str(taskScore[1]))
			groupScore[0] += taskScore[0]
			groupScore[1] += taskScore[1]
			taskScore = [0,0]

			if actindex == len(tasks) and groupResultTask is not None:
				groupResultTask.set('Score',str(groupScore[0])+'/'+str(groupScore[1]))
			actindex +=1

		self.__resultXMLRoot.set('Score',str(scoreMax)+'/'+str(scoreResult))
		with queueLock:
			#self.debug_xml(self.__resultXMLRoot)
			self.__socket.send(ET.tostring(self.__resultXMLRoot))
			self.__socket.shutdown(socket.SHUT_RDWR)

	def debug_xml(self, xmlObject):
		print(xmlObject.tag,xmlObject.attrib)
		if xmlObject.text:
			print(xmlObject.tag,xmlObject.text)
		for item in xmlObject.findall('./*'):
			self.debug_xml(item)


class newWorkerThread (threading.Thread):
	def __init__(self, threadID, name, q):
		threading.Thread.__init__(self)
		self.threadID = threadID
		self.name = name
		#thread know the queue
		self.q = q
	def run(self):
		print("Starting " + self.name)
		#call process_data to get and run a process from the queue
		process_data(self.name, self.q)
		print("Exiting " + self.name)

class ClientThread(threading.Thread):
	def __init__(self, ip, port, socket):
		threading.Thread.__init__(self)
		self.ip = ip
		self.port = port
		self.socket = socket
		#self.socket.settimeout(5)
		print(str(datetime.datetime.now()) +"=>  Connect client: "+ip+":"+str(port))

	def run(self):
		global exitFlag
		while not exitFlag:
			try:
				data = self.socket.recv(1024)
			except:
				break

			#get command (eg. exit, exercise xml reload) or exercise data (form -> exerciseNumber,labNumber,neptun,passw)
			if data == b'exit\n' or not data:
				break
			elif data == b'reload\n':
				with queueLock:
					reloadExerciseXMLs()
			elif data == b'stat\n':
				count = 0
				for user in runEvulatorUser:
					if user:
						count +=1
				print('Free user: 20/'+str(count))
			elif data != b'':
				with queueLock:
					params = str(data)[2:-3].split(',')
					if len(params) == 3 or len(params) == 4:
						try:
							int(params[0])
							int(params[1])
						except:
							self.socket.send(b'Parse error')
							break
					else:
						self.socket.send(b'Argument number error')
						break

					#create process with (exerciseNumber,labNumber,loginname,solution ) param
					if len(params) == 3:
						proc = Process(self.socket,int(params[0]), params[1],params[2],None)
					elif len(params) == 4:
						proc = Process(self.socket,int(params[0]), params[1],params[2],params[3])

					if proc.error:
						self.socket.send(b'Source parse error')
						break
					#put the queue, one thread will process it
					workQueue.put(proc)

		#self.socket.shutdown(socket.SHUT_RDWR)
		self.socket.close()
		print(str(datetime.datetime.now()) +"=>  Disconnect client: "+ip+":"+str(port))


def reloadExerciseXMLs():
	global exerciseRoots
	expath = workDir + '/exercises/'
	#print('[LOAD Exercises from: '+expath+']')
	for file in os.listdir(expath):
		if file.endswith('.xml') and file.startswith('exercises.') and len(file.split('.')) == 3:
			index = int(file.split('.')[1])
			if exerciseRoots[index] is None or exerciseRootsModifiedTime[index] < os.path.getmtime(expath + file):
				try:
					exerciseRoots[index] = ET.parse(expath + file).getroot()
					exerciseRootsModifiedTime[index] = os.path.getmtime(expath + file)
					print('Loaded: '+str(index))
				except:
					print('XML parse error: '+str(index))
					if exerciseRoots[index] is None:
						global exitFlag
						exitFlag = True


def process_data(threadName, q):
	global exitFlag
	while not exitFlag:
		data = None
		if not workQueue.empty():
			with queueLock:
				if not workQueue.empty():
					#get process
					data = q.get()
			if data is not None:
				#run it
				data.run(threadName)
				data.userpool()
				if not data.error:
					#evaluateAll and send result back to the socket
					data.evaluateAll()
				else:
					data.getSocket().shutdown(socket.SHUT_RDWR)
		else:
			time.sleep(0.1)


#load exercise xml file root
reloadExerciseXMLs()

if not exitFlag:
	#create socket
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serversocket:
		serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

		#listening on hostname:5555
		serversocket.bind(('' if args.allnetwork else socket.gethostname(), args.port))

		#active socket limit
		serversocket.listen(5)
		# Create new threads
		for threadID in range(1,threadNumber+1):
			thread = newWorkerThread(threadID, "Thread-"+str(threadID), workQueue)
			thread.start()
			threads.append(thread)

		print('[Serversocket open]')
		try:
			while True:
				(clientsock, (ip, port)) = serversocket.accept()
				newthread = ClientThread(ip, port, clientsock)
				newthread.start()
				threads.append(newthread)
		except:
			exitFlag = True
			serversocket.shutdown(socket.SHUT_RDWR)
			serversocket.close()
			print('[Serversocket close]')


print('Wait for queue to empty')
while not workQueue.empty():
	pass

print('Wait for all threads to complete')
for t in threads:
	t.join()
print("Exiting Main Thread")
