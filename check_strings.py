#!/usr/bin/python
#encoding:utf-8
#Filename: check_strings.py

import uuid
import shutil
import subprocess
import threading
import os
import time
import sys
import re
from xc_helper_base import XCProject
from xc_helper_base import StringResource
from xc_helper_base import StringObject
from xc_helper_base import message
from build_strings import StringsBuilder

from collections import OrderedDict

#################################################
def threadWorker(strChker, tid):
	message().info('Thread-#%d started' % tid)
	stringResBuilder = StringsBuilder(strChker.xcodeproj)

	trimCommentShell = os.path.abspath(os.path.join(os.path.dirname(__file__), 'trimComment.sh'))
	if not os.path.isfile(trimCommentShell):
		message().error('File "%s" not exists!' % trimCommentShell)
		sys.exit(1)

	while True:

		f = strChker.nextFile()
		if f == None:
			message().info('Thread-#%d Done' % tid)
			return

		p = subprocess.Popen([trimCommentShell, f['path']], stdout=subprocess.PIPE)
		stdout, stderr = p.communicate()
		if p.returncode != 0:
			message().error('Fail to trim comments, file: "%s"' % f['path'])
			message().info(stdout)
			continue

		strings = strChker.availableStrings()
		for name in strings:
			if f['type'] == 'sourcecode':
				grepRegex = '\\b%s\\b|\\b%s\\b' % (stringResBuilder.macroNameForString(name), name)
				
			elif f['type'] == 'plist':
				grepRegex = '\\b%s\\b' % name

			if re.search(grepRegex, stdout):
				strChker.markStringBeingUsed(name)

		os.write(1, '#')


#####################################################################################
class StringsChecker(object):
	"""docstring for StringsChecker"""

	XCStringsBeingUsedState = 0xff

	def __init__(self, xcodeproj):
		super(StringsChecker, self).__init__()
		self.xcodeproj = xcodeproj
		self.strings = StringResource(xcodeproj).loadConfig()

	def checkStringsConsistent(self, defaultLanguage='en'):
		''' check if strings resource in other languages is consistent with default language '''

		message().info('Checking strings resources consistent ...')
		defaultStrings = self.strings.loadStrings(defaultLanguage, True)

		for lang, path in self.strings.stringsFiles.items():
			if lang == defaultLanguage:
				continue
			message().info('checking %s' % path)
			localStrings = self.strings.loadStrings(lang, True)
			localStrings = OrderedDict((k, v) for k, v in localStrings.items() if defaultStrings.has_key(k))
			self.strings.saveToFile(lang, localStrings, False)

		message().info('Check consistent Done.')

	def checkUselessStrings(self, defaultLanguage='en'):
		self.stringsObjects = self.strings.loadStrings(defaultLanguage, True)
		self.loadCheckingFiles()

		self.fileLock	 = threading.Lock()
		self.stringsLock = threading.Lock()
		thread_pool = []
		#start 10 threads
		for i in range(10):
			th = threading.Thread(target=threadWorker, args=(self, i))
			thread_pool.append(th)

		message().info('Start checking unused strings ...')
		for th in thread_pool:
			th.start()


		for th in thread_pool:
			threading.Thread.join(th)

		counter = 0
		for key, strobj in self.stringsObjects.items():
			if strobj.state != StringsChecker.XCStringsBeingUsedState:
				strobj.state = StringObject.XCStringsUnusedState
				counter = counter + 1

		self.strings.saveToFile(defaultLanguage, self.stringsObjects, True)
		self.checkStringsConsistent(defaultLanguage)

		message().info('Found [%d] useless strings, Done!' % counter)



	def loadCheckingFiles(self):
		""" load files that need to check if using strings resource """
		self.pendingFiles =[]
		for f in self.xcodeproj.getfiles():
			if f.has_key('lastKnownFileType') and f['lastKnownFileType'][0:11] == 'sourcecode.':
				self.pendingFiles.append({'path':os.path.join(self.xcodeproj.projectHome, f['full_path']), 'type':'sourcecode'})

			elif os.path.basename(f['path']) == 'InAppSettings.bundle':
				boundlePath = os.path.join(self.xcodeproj.projectHome, f['full_path'])
				for root, dirs, fs in os.walk(boundlePath, True):
					for fileName in fs:
						if os.path.splitext(fileName)[1] == '.plist':
							self.pendingFiles.append({'path':os.path.join(root, fileName), 'type':'plist'})


	def nextFile(self):
		f = None
		self.fileLock.acquire()
		if len(self.pendingFiles) > 0:
			f = self.pendingFiles[0]
			del self.pendingFiles[0]
		self.fileLock.release()
		return f

	def availableStrings(self):
		self.stringsLock.acquire()
		dic = OrderedDict((k, v) for k, v in self.stringsObjects.items() if v.state != StringsChecker.XCStringsBeingUsedState)
		self.stringsLock.release()
		return dic.keys()


	def markStringBeingUsed(self, strName):
		self.stringsLock.acquire()
		if self.stringsObjects.has_key(strName):
			self.stringsObjects[strName].state = StringsChecker.XCStringsBeingUsedState
		self.stringsLock.release()



		
