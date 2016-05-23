#!/usr/bin/python3
import subprocess
import xml.etree.ElementTree as ET
import evaluateMode
import queue
import threading
import socket
import os
import time
import datetime
import argparse
import sys
import re
from glob import iglob

from util.xmlHelper import ETappendChildTruncating

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
runEvaluatorUser = [True] * 20

#define thread work variable
exitFlag = False
threads = []
queueLock = threading.Lock()


'''If socket get a process message it convert to Process object'''
class Process:
	error = False

	'''Create inputs to preprocessor and initialize result XML root'''
	def __init__(self,socket, exerciseNumber, labNumber,schema,sol):
		self.__timeout = False
		self.resultXMLRoot = None
		self.__user = -1
		self.__channelRoots = {}
		self.__replace = {}

		self.__socket = socket
		self.__labNumber = labNumber
		self.__exerciseNumber = exerciseNumber

		self.__replace['schema'] = schema
		self.__replace['passw'] = 'PASSWORD_REPLACE_ME'
		self.__replace['workdir'] = workDir
		self.__replace['sol'] = sol
		self.__replace['eid'] = str(exerciseNumber)

		print('User: '+schema + ' Lab: '+str(labNumber) + ' ExNu: '+str(exerciseNumber))

		self.resultXMLRoot = ET.Element('exercise',{'EID':str(exerciseNumber),'LID':str(labNumber), 'User':schema})

		if labNumber != '1' and sol is not None and not os.path.isfile(sol):
			print('No exist sol file')
			self.resultXMLRoot.set('error','No exist sol file: '+sol)
			self.error = True
			return

		if exerciseRoots[exerciseNumber] is None:
			print('No exist exercise.N.xml')
			self.resultXMLRoot.set('error','No exist exercise.N.xml: '+str(exerciseNumber))
			self.error = True
			return

		if exerciseRoots[exerciseNumber].find('./exercise[@n="'+labNumber+'"]') is None:
			print('No exist exercise')
			self.resultXMLRoot.set('error','No exist lab in '+str(exerciseNumber)+' exercise: '+labNumber)
			self.error = True
			return

		user = ''
		if labNumber == '1':
			user = 'ertekelo'
		else:
			if args.allnetwork:
				for i in range(0, 19):
					if runEvaluatorUser[i]:
						runEvaluatorUser[i] = False
						self.__user = i
						user = 'DB_USERNAME_REPLACE_ME_0'+str(i) if i < 10 else 'DB_USERNAME_REPLACE_ME_'+str(i)
						break
			if user == '':
				user = 'DB_USERNAME_REPLACE_ME'

		self.__replace['user'] = user

		if self.__user != -1:
			self.__replace['portNumber'] = str(15000 + self.__user)
		else:
			self.__replace['portNumber'] = str(14999)

		# Main script can either be defined in the exercise tag as well as a children script[@entry='main'] tag.
		if exerciseRoots[exerciseNumber].find('./exercise[@n="'+labNumber+'"]').get('scriptPath') is not None:
			self.__channelRoots['Main'] = self.script(exerciseRoots[exerciseNumber].find('./exercise[@n="'+labNumber+'"]'))
			print('*')
		for scriptInit in exerciseRoots[exerciseNumber].findall('./exercise[@n="'+labNumber+'"]/script'):
			channelName=scriptInit.get('channelName') if scriptInit.get('entry') != 'main' else 'Main'
			if channelName not in self.__channelRoots:
				self.__channelRoots[channelName] = self.script(scriptInit)
			else:
				print('Warning: duplicate definition skipped for channel ' + channelName + ' at Lab: ' + str(labNumber) + ' ExNu: ' + str(exerciseNumber))

		if 'Main' not in self.__channelRoots:
			self.resultXMLRoot.set('error','No main script setting (missing scriptpath or/and arguments...)')
			self.error = True
			return

	def getSocket(self):
		return self.__socket

	def script(self,target):
		channelRoot = {}
		channelRoot['channelFormat'] = target.get('channelFormat') if target.get('channelFormat') is not None else 'xml'
		channelRoot['Path'] = self.replaceIDs(target.get('scriptPath')) if target.get('scriptPath') is not None else ''
		channelRoot['ParameterString'] = self.replaceIDs(target.get('arguments')) if target.get('arguments') is not None else ''
		channelRoot['Entry'] = target.get('entry')
		channelRoot['InputStream'] = []
		channelRoot['referenceChannel'] = target.get('referenceChannel')
		channelRoot['command'] = target.get('command')

		for input in target.findall('./inputstream'):
			channelRoot['InputStream'].append({'fromXML':False,'text':self.replaceIDs(input.text)} if input.get('fromXML') is None else {'fromXML':True,'text':self.replaceIDs(input.get('fromXML'))})

		return channelRoot

	def replaceIDs(self, param):
		for key, value in self.__replace.items():
			if value is not None:
				param = param.replace('$' + key, value)
		return param

	def userpool(self):
		with queueLock:
			if self.__user != -1:
				runEvaluatorUser[self.__user] = True

	def generateInputStreamFromXML(self, XMLPath, channelName):
		try:
			file = open(XMLPath, 'r').read()
			xmlRoot = ET.fromstring(file)
			result = ['print|||<tasks>']
			for task in xmlRoot.findall('.//task'):
				result.append('print|||<task n="'+task.get('n')+'">')
				if len(task.findall('./subtask')) == 0:
					result.append('print|||<![CDATA[')
					result.append(task.text.strip())
					result.append('print|||]]>')
				else:
					for subtask in task.findall('./subtask'):
						result.append('print|||<subtask n="'+subtask.get('n')+'">')
						result.append('print|||<![CDATA[')
						result.append(subtask.text.strip())
						result.append('print|||]]>')
						result.append('print|||</subtask>')
				result.append('print|||</task>')
			result.append('print|||</tasks>')
			return '\n'.join(result)
		except:
			self.error = True
			self.sendErrorMessage(channelName + '[Script inputStream error]\nDetails\n'+str(sys.exc_info()))
			return None


	def runSubProcess(self,channelName):
		channel = self.__channelRoots[channelName]
		print('[Wait '+channel['Path']+' script ...]')
		inputStream = ''
		for input in channel['InputStream']:
			if input['fromXML']:
				inputFromXML = self.generateInputStreamFromXML(input['text'], channelName)
				if inputFromXML is None:
					return
				inputStream += inputFromXML + '\n'
			else:
				inputStream += input['text'] + '\n'

		arguments = channel['ParameterString'].replace('=',' ')
		arguments = arguments.split(' ')
		arguments.insert(0,channel['Path'])

		#print(arguments)
		if channel['Entry'] == 'con':
			try:
				channel['con'] = subprocess.Popen(arguments,stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=subprocess.PIPE, universal_newlines=True)
				time.sleep(1)
				print(channelName + ' =>  [Script running]')
			except FileNotFoundError:
				self.error = True
				self.sendErrorMessage('[Script not found for channel ' + channelName + ': ' + arguments[0] + ']')
				return
		elif channel['referenceChannel'] is not None:
			if channel['command'] == 'exit':
				print('[Killed: '+channel['referenceChannel']+']')
				self.__channelRoots[channel['referenceChannel']]['con'].kill()
		else:
			try:
				with subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=subprocess.PIPE, universal_newlines=True) as proc:
					try:
						channel['out'], channel['error'] = proc.communicate(input=inputStream,timeout=60)
					except subprocess.TimeoutExpired:
						self.__timeout = True
						print(channelName + ' => [Script timeout]')
						proc.kill()
						return
			except FileNotFoundError:
				self.error = True
				self.sendErrorMessage('[Script not found for channel ' + channelName + ': ' + arguments[0] + ']')
				return
			print(channelName + ' =>  [Script run finish]')



		if channel['channelFormat'] == 'xml' and channel['Entry'] != 'con':
			channel['out'] = channel['out'][channel['out'].find('<tasks>'):channel['out'].find('</tasks>')+8]
			#print(channel['out'])
			try:
				channel['out'] = ET.fromstring(channel['out'])
			except:
				self.error = True
				self.sendErrorMessage('[Script output parse error]\nDetails\n'+str(sys.exc_info())+'\nsubprocess:\n'+channel['error'] if 'error' in channel else '')
				return

	'''Run the given script with given arguments and inputstream'''
	def run(self, threadName):
		print(str(self.__user)+':'+self.__replace['schema']+'-'+str(self.__exerciseNumber)+': '+threadName)
		#run preScripts
		for key in self.__channelRoots:
			if (self.__channelRoots[key]['Entry'] == 'pre' or self.__channelRoots[key]['Entry'] == 'con'):
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
				return ''
			if self.__channelRoots[channel]['channelFormat'] == 'xml':
				output = self.getExerciseTask(task, self.__channelRoots[channel]['out'])
			else:
				output = self.__channelRoots[channel]['out']

		if output is None:
			output = ''

		#reformed result
		output = output.strip()
		if toLowerCase:
			output = output.lower()

		return output

	'''Run the given task solutions with specific evaluateMode functions'''
	def runEvaluateRutin(self,task,sol,solItem, result, resultTask):
		#get result from specified channel
		output = self.getChannelContent(solItem.get('channelName'),task)

		ETappendChildTruncating(resultTask, 'Output' if solItem.get('channelName') is None else solItem.get('channelName'), output, args.tooLong)

		if task.find('solution') is None:
			ET.SubElement(resultTask,'Required').text = task.find('description').text.strip() if task.find('description') is not None else ''
			return



		#remove white space characters from exercises.N.xml specified sol. element text
		solution = re.sub('\s+',' ',solItem.text).strip().lower()

		ET.SubElement(resultTask,'Required').text = solution

		with queueLock:
			#get the result from evaluateMode and score it with solution score
			try:
				res = getattr(evaluateMode, solItem.get('evaluateMode'))(output,solution,solItem.get('evaluateArgs'))
			except:
				print('Error in evaluateMode: ' + solItem.get('evaluateMode') + ' Task: '+task.get('n'))
				return result


		if sol is None or sol.get('score') is None:
			print('No score add in task solution: ' + task.get('n'))
			val = 0
		else:
			val = float(sol.get('score')) if (solItem.get('negation')==None and res) or (solItem.get('negation') and not res) else 0

		if val > result:
			result = val
		return result

	def getSolScore(self,task):
		if task.findall('solution')[0].get('score') is None:
			print('missing score in Solution element in:'+task.get('n'))
			return 0
		return float(task.findall('solution')[0].get('score'))

	def getScoreIndex(self,sol):
		scoreindex = 0
		if sol is None:
			return scoreindex
		if sol.get('type') == 'bonus':
			scoreindex = 1
		elif sol.get('type') == 'minus':
			scoreindex = 2
		return scoreindex

	def scoreIt(self,task,sol,solItem, result,resultOut):
		scoreindex = self.getScoreIndex(sol)
		result[scoreindex] = self.runEvaluateRutin(task,sol,solItem, result[scoreindex], resultOut)
		if sol.get('type') is not None:
			resultOut.set('type',sol.get('type'))
		if solItem.get('negation') is not None:
			resultOut.set('negation', 'True')
		resultOut.set('result',str(result))
		return result[scoreindex]

	'''Calc the score'''
	def evaluate(self,task,resultTask):
		result = [0,0,0]

		#dependency check
		dependencyOk = True
		for dep in task.findall('dependency'):
			target = self.resultXMLRoot.find('.//*[@n="'+dep.get('for')+'"]')
			if target is not None and int(target.get('Score').split('/')[1]) < int(dep.get('minScore')):
				dependencyOk = False
				ET.SubElement(resultTask,'Required').text = 'Dependency failed: task:'+dep.get('for')+' minScore:'+dep.get('minScore')
				break

		if not dependencyOk:
			return result

		#if manual test
		if task.find('solution') is None:
			self.runEvaluateRutin(task,None,task, 0, resultTask)
			return result
		#if automatic test
		#solutionItems connect together with AND logic
		#solutions connect together with OR logic
		for sol in task.findall('solution'):
			if len(sol.findall('solutionItem')) == 0:
				resultSol = ET.SubElement(resultTask,'Solution',{'method':sol.get('evaluateMode')})
				self.scoreIt(task,sol,sol, result, resultSol)
			else:
				oldresult = result[self.getScoreIndex(sol)]
				notBreak = True
				resultSol = ET.SubElement(resultTask,'Solution')
				for solItem in sol.findall('solutionItem'):
					result[self.getScoreIndex(sol)] = 0
					resultSubSol = ET.SubElement(resultSol,'SubSolution',{'method':solItem.get('evaluateMode')})
					if self.scoreIt(task,sol,solItem, result, resultSubSol) == 0:
						notBreak = False
				# if a single solutionItem scored for 0 points, this solution gets 0 points.
				if not notBreak:
					result[self.getScoreIndex(sol)] = 0
				# if the current solution scores less than the previous, then retain the previous score
				if result[self.getScoreIndex(sol)] < oldresult:
					result[self.getScoreIndex(sol)] = oldresult

		return [result[0] + result[1] - result[2], self.getSolScore(task)]


	def sendErrorMessage(self, message):
		with queueLock:
			try:
				self.__socket.send(message.encode())
			except:
				print('Couldnt send data from socket\n'+str(sys.exc_info()))
			print(message)
			try:
				self.__socket.shutdown(socket.SHUT_RDWR)
			except:
				print('Couldnt close the socket')



	'''Create result output with call evaluate function to every task, listen to reference'''
	def evaluateAll(self):
		if self.__timeout:
			self.sendErrorMessage('TimeOut')
			return

		scoreResult = 0
		scoreMax = 0
		resultTasks = ET.SubElement(self.resultXMLRoot,'taskDetails')
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
				Description.text = task.find('./description').text if task.find('./description') is not None else ''
				# add source code here
				output = self.getChannelContent('Source', task, False)
				if output != '':
					ETappendChildTruncating(resultTask, 'Source', output, args.tooLong)
				# go on to scoring
				actScore = self.evaluate(task,resultTask)
				taskScore[0] = actScore[1]
				taskScore[1] = actScore[0]
				scoreResult += actScore[0]
				scoreMax += actScore[1]
			else:
				taskDesc = ET.SubElement(resultTask,'Description')
				taskDesc.text = task.find('./description').text if task.find('./description') is not None else ''

				for subtask in task.findall('./subtask'):
					resultSubTask = ET.SubElement(resultTask,'SubTask',{'n':subtask.get('n')})
					Description = ET.SubElement(resultSubTask,'Description')
					Description.text = subtask.find('./description').text if subtask.find('./description') is not None else ''
					TaskText = ET.SubElement(resultSubTask,'TaskText')
					TaskText.text = subtask.find('./tasktext').text if subtask.find('./tasktext') is not None else ''
					# add source code here
					output = self.getChannelContent('Source', subtask, False)
					if output != '':
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

		self.resultXMLRoot.set('Score',str(scoreMax)+'/'+str(scoreResult))
		with queueLock:
			#self.debug_xml(self.resultXMLRoot)
			self.__socket.send(ET.tostring(self.resultXMLRoot))
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
				count = sum(runEvaluatorUser)
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
						self.socket.send(ET.tostring(proc.resultXMLRoot))
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
	for path in iglob(expath + 'exercises.*.xml'):
		index = int(path.rsplit('.', 2)[1])
		if exerciseRoots[index] is None or exerciseRootsModifiedTime[index] < os.path.getmtime(path):
			try:
				exerciseRoots[index] = ET.parse(path).getroot()
				exerciseRootsModifiedTime[index] = os.path.getmtime(path)
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
					try:
						data.getSocket().shutdown(socket.SHUT_RDWR)
					except:
						print('socket is closed')
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
