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

#configure
exerciseXMLsPath = '/exercises/'
workQueue = queue.Queue(10)
threadNumber = 3


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

	'''With exerciseNumber, labNumber, username, password arguments fill scriptPath, scriptParameterString, scriptInputStream from exerciseXML root'''
	def __init__(self, exerciseNumber, labNumber,user,passw,sol):
		#fill the defined variable with specific data from exerciseRoots
		self.__labNumber = labNumber
		self.__exerciseNumber = exerciseNumber
		self.__scriptPath = exerciseRoots[exerciseNumber].find('./exercise[@n="'+labNumber+'"]').get('scriptPath')
		self.__scriptParameterString = exerciseRoots[exerciseNumber].find('./exercise[@n="'+labNumber+'"]').get('arguments')
		#fill input stream, \n mean enter in console
		for input in exerciseRoots[exerciseNumber].findall('./exercise[@n="'+labNumber+'"]/inputstream'):
			self.__scriptInputStream += '\n'+input.text

		self.__scriptInputStream = self.__scriptInputStream.replace('$user',user).replace('$passw', passw)


		#print(self.__scriptInputStream)
		if sol != None:
			self.__scriptInputStream = self.__scriptInputStream.replace('$sol', sol) + '\n'
			sol = open(sol, 'r').read()
			self.__sourceRoot = ET.fromstring(sol[sol.find('<tasks>'):sol.find('</tasks>')+8].replace('prompt',''))
		else:
			self.__scriptInputStream = self.__scriptInputStream + '\n'

		self.__resultXMLRoot = ET.Element('exercise',{'EID':str(exerciseNumber),'LID':str(labNumber), 'User':user})


	'''Run the given script with given argument and inputstream and save the xml convert output root'''
	def run(self):
		#run background subprocess with given configure
		print('[Wait '+self.__scriptPath+' script ...]')
		with subprocess.Popen([self.__scriptPath,self.__scriptParameterString], stdin=subprocess.PIPE, stdout=subprocess.PIPE,stderr=subprocess.PIPE, universal_newlines=True) as proc:
			try:
				self.__outs, self.__errs = proc.communicate(input=self.__scriptInputStream,timeout=60)
			except subprocess.TimeoutExpired:
				self.__timeout = True
				print('[Script timeout]')
				proc.kill()

		if self.__timeout:
			return
		print('[Script run finish]')
		#Cut everything before <tasks> element and after </tasks> element
		self.__outs = self.__outs[self.__outs.find('<tasks>'):self.__outs.find('</tasks>')+8]

		self.__PPORoot = ET.fromstring(self.__outs)

	'''Get the tasknumber/subtasknumber output from preprocessor output'''
	def getExerciseTask(self,task, rootObject):
		result = rootObject.find('.//task[@n="'+task.get('n')+'"]')
		return result.text if result != None else None

	def getSourceOrOutput(self,solItem,task):
		if solItem.get('fromSource') == None:
			output = self.getExerciseTask(task, self.__PPORoot)
		else:
			output = self.getExerciseTask(task, self.__sourceRoot)
		return output

	def runEvaluateRutin(self,task,sol,solItem, result, bonus, resultTask):
		output = self.getSourceOrOutput(solItem,task)
		if output != None:
			output = re.sub('\s+$','',re.sub('^\s+','',output)).lower()
		ET.SubElement(resultTask,'output' if solItem.get('fromSource') == None else 'source').text = output

		if task.find('solution') == None:
			ET.SubElement(resultTask,'input').text = re.sub('\s+$','',re.sub('^\s+','',task.find('description').text))
			return


		if output != None:
			#remove white space characters from exercises.N.xml specified sol. element text
			solution = re.sub('\s+',' ',solItem.text).strip(' ').lower()
			ET.SubElement(resultTask,'input').text = solution

			queueLock.acquire()
			res = getattr(evaluateMode, solItem.get('evaluateMode'))(output,solution)
			val = float(sol.get('score')) if (solItem.get('negation')==None and res) or (solItem.get('negation') and not res) else 0
			queueLock.release()

			if sol.get('bonus') != None and bonus == 0:
				bonus = val
			elif sol.get('bonus') == None and result == 0:
				result = val
		return [result,bonus]

	'''Calc the score'''
	def evaluate(self,task,resultTask):

		#if manual test
		if task.find('solution') == None:
			self.runEvaluateRutin(task,None,task, 0, 0, resultTask)
			return '-'

		result = [0,0]

		for sol in task.findall('solution'):
			if len(sol.findall('solutionItem')) == 0:
				resultSol = ET.SubElement(resultTask,'solution',{'method':sol.get('evaluateMode')})
				result = self.runEvaluateRutin(task,sol,sol, result[0], result[1], resultSol)
				resultSol.set('result',str(result))
			else:
				oldresult = result[0]
				resultSol = ET.SubElement(resultTask,'solution')
				for solItem in sol.findall('solutionItem'):
					result[0] = 0
					resultSubSol = ET.SubElement(resultSol,'subsolution',{'method':solItem.get('evaluateMode')})
					result = self.runEvaluateRutin(task,sol,solItem, result[0], result[1], resultSubSol)
					resultSubSol.set('result',str(result))
					if result[0] == 0:
						break
				if result[0] < oldresult:
					result[0] = oldresult

		return str(result[0] + result[1])



	'''Create result output with call evaluate function to every task'''
	def evaluateAll(self):
		if self.__timeout:
			return 'TimeOut'
		scoreTable = ''
		resultTasks = ET.SubElement(self.__resultXMLRoot,'taskDetails')
		exercise = exerciseRoots[self.__exerciseNumber].find('./exercise[@n="'+self.__labNumber+'"]')
		tasks = exercise.findall('.//task') if exercise.get('reference') == None else exerciseRoots[int(exercise.get('reference'))].findall('./exercise[@n="'+self.__labNumber+'"]//task')
		for task in tasks:
			if task.get('reference') != None:
				task = exerciseRoots[int(task.get('reference'))].find('./exercise[@n="'+self.__labNumber+'"]//task[@id="'+task.get('reference-id')+'"]')
			resultTask = ET.SubElement(resultTasks,'task',{'n':task.get('n')})
			scoreTable += task.get('n') + ' = ' + self.evaluate(task,resultTask) + ' pont\n'



		# for task in exerciseRoots[self.__exerciseNumber].findall('./exercise[@n="'+self.__labNumber+'"]/taskgroup'):
			# noSubTask = True
			# if task.get('reference') != None:
				# task = exerciseRoots[int(task.get('reference'))].find('./exercise[@n="'+self.__labNumber+'"]/taskgroup[@n="'+task.get('n')+'"]')


			# resultTask = ET.SubElement(resultTasks,'taskgroup',{'n':task.get('n')})

			# for subtask in task.findall('task'):
				# resultSubTask = ET.SubElement(resultTask,'task',{'n':subtask.get('n')})
				# if subtask.get('reference') != None:
					# subtask = exerciseRoots[int(subtask.get('reference'))].find('./exercise[@n="'+self.__labNumber+'"]/taskgroup[@n="'+task.get('n')+'"]/task[@n="'+subtask.get('n')+'"]')
				# scoreTable += task.get('n') + ':' + subtask.get('n') + ' = ' + self.evaluate(subtask, task.get('n'),resultSubTask) + ' pont\n'
				# noSubTask = False

			# if noSubTask:
				# scoreTable += task.get('n') + ' = ' + self.evaluate(task, task.get('n'),resultTask) + ' pont\n'

		ET.SubElement(self.__resultXMLRoot,'scoreTable').text = scoreTable
		print(ET.tostring(self.__resultXMLRoot))
		return scoreTable

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
		self.socket.settimeout(5)
		print("Connect client: "+ip+":"+str(port))

	def run(self):
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
				exerciseRoots = reloadExerciseXMLs()
				queueLock.release()
			elif data != b'':
				queueLock.acquire()
				params = str(data)[2:-3].split(',')
				#create process with (exerciseNumber,labNumber,loginname,passw, solution ) param
				if len(params) == 4:
					proc = Process(int(params[0]), params[1],params[2],params[3],None)
				elif len(params) == 5:
					proc = Process(int(params[0]), params[1],params[2],params[3],params[4])

				#put the queue, one thread will process it
				workQueue.put(proc)
				queueLock.release()

		self.socket.shutdown(socket.SHUT_RDWR)
		self.socket.close()
		print("Disconnect client: "+ip+":"+str(port))


def reloadExerciseXMLs():
	exercises = [None] * 50
	expath = os.path.dirname(os.path.realpath(__file__)) + exerciseXMLsPath
	print('[LOAD Exercises from: '+expath+']')
	for file in os.listdir(expath):
		if file.endswith('.xml') and file.startswith('exercises.') and len(file.split('.')) == 3:
			index = int(file.split('.')[1])
			exercises[index] = ET.parse(expath + file).getroot()
			print('Loaded: '+str(index))
	return exercises


def process_data(threadName, q):
	while not exitFlag:
		if not workQueue.empty():
			queueLock.acquire()
			if not workQueue.empty():
				#get process
				data = q.get()
			queueLock.release()
			#run it
			data.run()
			#send result data to anywhere
			print('Result:')
			print(data.evaluateAll())
		else:
			time.sleep(0.1)

#define thread work variable
exitFlag = False
threadNumber = 3
threads = []
queueLock = threading.Lock()

#load exercise xml file root
exerciseRoots = reloadExerciseXMLs()

#create socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serversocket:
	serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

	#listening on hostname:5555
	serversocket.bind((socket.gethostname(), 5555))

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
