#!/usr/bin/python3
import subprocess
import xml.etree.ElementTree as ET
import evaluateMode
import queue
import threading
import socket
import contextlib
import os
import re
import time
import datetime
import argparse

parser = argparse.ArgumentParser('AKÉP')
parser.add_argument('-p','--port', metavar='port', help='Server listener portnumber', default=5555, type=int)
parser.add_argument('-E','--Epath',metavar='path', help='Relative exercise XMLs path', default='/../exercises/', type=str)
parser.add_argument("-a","--allnetwork", help="Listening on all interface", action='store_true')
args = parser.parse_args()

print('Listen: '+('all interface' if args.allnetwork else 'localhost') + ' on port:'+str(args.port))

#configure
RelativeExerciseXMLsPath = args.Epath
workQueue = queue.Queue(10)
threadNumber = 3
exerciseRoots = [None] * 50

#define thread work variable
exitFlag = False
threads = []
queueLock = threading.Lock()


'''If socket get a process message it convert to Process object'''
class Process:
	__scriptPath = ''
	__scriptParameterString = ''
	__scriptInputStream = ''
	__PPORoot = None
	__labNumber = ''
	__exerciseNumber = 0
	__sourceRoot = None
	__timeout = False
	__resultXMLRoot = None
	__socket = None
	__scheme = ''
	error = False

	'''Create inputs to preprocessor and initialize result XML root'''
	def __init__(self,socket, exerciseNumber, labNumber,schema,sol):
		self.__socket = socket
		self.__labNumber = labNumber
		self.__exerciseNumber = exerciseNumber
		self.__scheme = schema

		#fill the defined variable with specific data from exerciseRoots
		self.__scriptPath = exerciseRoots[exerciseNumber].find('./exercise[@n="'+labNumber+'"]').get('scriptPath')
		self.__scriptParameterString = exerciseRoots[exerciseNumber].find('./exercise[@n="'+labNumber+'"]').get('arguments')
		#fill input stream, \n mean enter in console
		for input in exerciseRoots[exerciseNumber].findall('./exercise[@n="'+labNumber+'"]/inputstream'):
			self.__scriptInputStream += '\n'+input.text

		#replace spific word
		if labNumber == '1':
			user = 'ertekelo'
		else:
			user = 'DB_USERNAME_REPLACE_ME'

		self.__scriptInputStream = self.__scriptInputStream.replace('$schema',schema).replace('$user',user).replace('$passw', 'PASSWORD_REPLACE_ME')
		self.__scriptInputStream = self.__scriptInputStream.replace('$sol', sol if sol != None else '') + '\n'

		if sol != None:
			sol = open(sol, 'r').read()
			#student optional sourcecode channel
			try:
				self.__sourceRoot = ET.fromstring(sol[sol.find('<tasks>'):sol.find('</tasks>')+8].replace('prompt',''))
			except:
				self.error = True
				return

		#Output result XML to the socket caller
		self.__resultXMLRoot = ET.Element('exercise',{'EID':str(exerciseNumber),'LID':str(labNumber), 'User':schema})


	'''Run the given script with given arguments and inputstream'''
	def run(self, threadName):
		#run background subprocess with given configure
		print(self.__scheme+'-'+str(self.__exerciseNumber)+': '+threadName+'=> [Wait '+self.__scriptPath+' script ...]')
		with subprocess.Popen([self.__scriptPath,self.__scriptParameterString], stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=subprocess.PIPE, universal_newlines=True) as proc:
			try:
				self.__outs, self.__errs = proc.communicate(input=self.__scriptInputStream,timeout=60)
			except subprocess.TimeoutExpired:
				self.__timeout = True
				print(str(datetime.datetime.now()) +'=>  [Script timeout]')
				proc.kill()

		if self.__timeout:
			return
		print(str(datetime.datetime.now()) + '=>  [Script run finish]')
		#Cut everything before <tasks> element and after </tasks> element
		self.__outs = self.__outs[self.__outs.find('<tasks>'):self.__outs.find('</tasks>')+8]

		try:
			self.__PPORoot = ET.fromstring(self.__outs)
		except:
			self.error = True
			queueLock.acquire()
			self.__socket.send(b'Student output parse error')
			print('Student output parse error')
			self.__socket.shutdown(socket.SHUT_RDWR)
			queueLock.release()
			return

	'''Get task output from rootObject (source or preprocessor output channel)'''
	def getExerciseTask(self,task, rootObject):
		result = rootObject.find('.//task[@n="'+task.get('n')+'"]')
		return result.text if result != None else None

	'''Get task output'''
	def getSourceOrOutput(self,solItem,task):
		if solItem.get('fromSource') == None:
			output = self.getExerciseTask(task, self.__PPORoot)
		else:
			output = self.getExerciseTask(task, self.__sourceRoot)
		return output

	'''Run the given task solutions with specific evaluateMode functions'''
	def runEvaluateRutin(self,task,sol,solItem, result, bonus, resultTask):
		#get result from specified channel
		output = self.getSourceOrOutput(solItem,task)
		if output != None:
			#reformed result
			output = re.sub('\s+$','',re.sub('^\s+','',output)).lower()

		ET.SubElement(resultTask,'Output' if solItem.get('fromSource') == None else 'Source').text = output

		if task.find('solution') == None:
			ET.SubElement(resultTask,'Required').text = re.sub('\s+$','',re.sub('^\s+','',task.find('description').text))
			return


		if output != None:
			#remove white space characters from exercises.N.xml specified sol. element text
			solution = re.sub('\s+',' ',solItem.text).strip(' ').lower()

			ET.SubElement(resultTask,'Required').text = solution

			queueLock.acquire()
			#get the result from evaluateMode and score it with solution score
			res = getattr(evaluateMode, solItem.get('evaluateMode'))(output,solution,solItem.get('evaluateArgs'))
			val = float(sol.get('score')) if (solItem.get('negation')==None and res) or (solItem.get('negation') and not res) else 0
			queueLock.release()

			#val add to bonusScore or resultScore depends by bonus attribute
			if sol.get('bonus') != None and val > bonus:
				bonus = val
			elif sol.get('bonus') == None and val > result:
				result = val
		return [result,bonus]

	'''Calc the score'''
	def evaluate(self,task,resultTask):
		result = [0,0]
		#if manual test
		if task.find('solution') == None:
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
				if result[0] < oldresult and notBreak:
					result[0] = oldresult
				elif not notBreak:
					result[0] = 0

		return [result[0] + result[1], float(task.findall('solution')[0].get('score'))]



	'''Create result output with call evaluate function to every task, listen to reference'''
	def evaluateAll(self):
		if self.__timeout:
			queueLock.acquire()
			self.__resultXMLRoot.set('TimeOut','True')
			self.__socket.send(ET.tostring(self.__resultXMLRoot))
			self.__socket.shutdown(socket.SHUT_RDWR)
			queueLock.release()
			return

		scoreResult = 0
		scoreMax = 0
		resultTasks = ET.SubElement(self.__resultXMLRoot,'taskDetails')
		exercise = exerciseRoots[self.__exerciseNumber].find('./exercise[@n="'+self.__labNumber+'"]')
		actExercise = exercise if exercise.get('reference') == None else exerciseRoots[int(exercise.get('reference'))].find('./exercise[@n="'+self.__labNumber+'"]')

		prevgroupTaskNode = None
		groupResultTask = None
		groupScore = [0,0]
		taskScore = [0,0]
		tasks = actExercise.findall('.//task')
		actindex = 1

		for task in tasks:
			groupTaskNode = exerciseRoots[self.__exerciseNumber].find('./exercise[@n="'+self.__labNumber+'"]//task[@n="'+task.get('n')+'"]/..')
			if task.get('reference') != None:
				task = exerciseRoots[int(task.get('reference'))].find('./exercise[@n="'+self.__labNumber+'"]//task[@id="'+task.get('reference-id')+'"]')

			if groupTaskNode == None:
				resultTask = ET.SubElement(resultTasks,'Task',{'n':task.get('n')})
				if groupResultTask != None:
					groupResultTask.set('Score',str(groupScore[0])+'/'+str(groupScore[1]))
					groupScore = [0,0]
					prevgroupTaskNode = None
			elif prevgroupTaskNode != groupTaskNode:
				if groupResultTask != None:
					groupResultTask.set('Score',str(groupScore[0])+'/'+str(groupScore[1]))
				prevgroupTaskNode = groupTaskNode
				groupResultTask = ET.SubElement(resultTasks,'TaskGroup',{'title':groupTaskNode.get('title')})
				resultTask = ET.SubElement(groupResultTask,'Task',{'n':task.get('n')})
				groupScore = [0,0]
			else:
				resultTask = ET.SubElement(groupResultTask,'Task',{'n':task.get('n')})

			TaskText = ET.SubElement(resultTask,'TaskText')
			TaskText.text = task.find('./tasktext').text if task.find('./tasktext') != None else ''

			if len(task.findall('./subtask')) == 0:
				Description = ET.SubElement(resultTask,'Description')
				Description.text = task.find('./description').text
				actScore = self.evaluate(task,resultTask)
				taskScore[0] = actScore[1]
				taskScore[1] = actScore[0]
				scoreResult += actScore[0]
				scoreMax += actScore[1]
			else:
				for subtask in task.findall('./subtask'):
					resultSubTask = ET.SubElement(resultTask,'SubTask',{'n':subtask.get('n')})
					Description = ET.SubElement(resultSubTask,'Description')
					Description.text = subtask.find('./description').text
					TaskText = ET.SubElement(resultSubTask,'TaskText')
					TaskText.text = subtask.find('./tasktext').text if subtask.find('./tasktext') != None else ''
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

			if actindex == len(tasks) and groupResultTask != None:
				groupResultTask.set('Score',str(groupScore[0])+'/'+str(groupScore[1]))
			actindex +=1

		self.__resultXMLRoot.set('Score',str(scoreMax)+'/'+str(scoreResult))
		queueLock.acquire()
		self.__socket.send(ET.tostring(self.__resultXMLRoot))
		self.__socket.shutdown(socket.SHUT_RDWR)
		queueLock.release()

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
				queueLock.acquire()
				reloadExerciseXMLs()
				queueLock.release()
			elif data != b'':
				queueLock.acquire()
				params = str(data)[2:-3].split(',')
				if len(params) == 3 or len(params) == 4:
					try:
						int(params[0])
						int(params[1])
					except:
						self.socket.send(b'Parse error')
						queueLock.release()
						break
				else:
					self.socket.send(b'Argument number error')
					queueLock.release()
					break

				#create process with (exerciseNumber,labNumber,loginname,solution ) param
				if len(params) == 3:
					proc = Process(self.socket,int(params[0]), params[1],params[2],None)
				elif len(params) == 4:
					proc = Process(self.socket,int(params[0]), params[1],params[2],params[3])

				if proc.error:
					self.socket.send(b'Source parse error')
					queueLock.release()
					break
				#put the queue, one thread will process it
				workQueue.put(proc)
				queueLock.release()

		#self.socket.shutdown(socket.SHUT_RDWR)
		self.socket.close()
		print(str(datetime.datetime.now()) +"=>  Disconnect client: "+ip+":"+str(port))


def reloadExerciseXMLs():
	global exerciseRoots
	expath = os.path.dirname(os.path.realpath(__file__)) + RelativeExerciseXMLsPath
	print('[LOAD Exercises from: '+expath+']')
	for file in os.listdir(expath):
		if file.endswith('.xml') and file.startswith('exercises.') and len(file.split('.')) == 3:
			index = int(file.split('.')[1])
			try:
				exerciseRoots[index] = ET.parse(expath + file).getroot()
				print('Loaded: '+str(index))
			except:
				print('XML parse error: '+str(index))
				if exerciseRoots[index] == None:
					global exitFlag
					exitFlag = True


def process_data(threadName, q):
	global exitFlag
	while not exitFlag:
		data = None
		if not workQueue.empty():
			queueLock.acquire()
			if not workQueue.empty():
				#get process
				data = q.get()
			queueLock.release()
			if data != None:
				#run it
				data.run(threadName)
				if not data.error:
					#evaluateAll and send result back to the socket
					data.evaluateAll()
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
