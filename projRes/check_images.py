#!/usr/bin/python
#encoding:utf-8
#Filename: check_images.py


import os
import sys
import re
import subprocess
import threading

from xc_helper_base import *
from build_images import ImagesBuilder



#################################################
def threadWorker(imagesInspector, tid):
	message().info('Thread-#%d started' % tid)

	while True:
		f = imagesInspector.nextFile()
		if f == None:
			message().info('Thread-#%d Done' % tid)
			return

		fileContent = trimComment(f['path'])
		images = imagesInspector.pendingCheckImages()
		for name in images.keys():
			if f['type'] == 'sourcecode':
				imageMacroName = '%sIMG_%s' % (imagesInspector.xcodeproj.projectClassPrefix(), name.upper())
				grepRegex = '\\b%s\\b|\\b%s\\b' % (imageMacroName, name)
				
			elif f['type'] in ('plist', 'xib'):
				grepRegex = '\\b%s\\b' % name

			if re.search(grepRegex, fileContent, re.IGNORECASE):
				imagesInspector.markImageBeingUsed(name)

		os.write(1, '#')


#####################################################################################



class ImagesInspector(object):
	"""docstring for ImagesInspector"""
	def __init__(self, xcodeproj):
		super(ImagesInspector, self).__init__()
		self.xcodeproj = xcodeproj


	def checkUselessImages(self):
		imgResMgr = ImagesResource(self.xcodeproj)
		self.images = imgResMgr.loadImagesResource()

		if len(self.images) == 0:
			message().info('No image resource, Done!')
			return

		self.loadCheckingFiles()

		self.fileLock	 = threading.Lock()
		self.imagesLock = threading.Lock()
		thread_pool = []
		#start 10 threads
		for i in range(10):
			th = threading.Thread(target=threadWorker, args=(self, i))
			thread_pool.append(th)

		message().info('Start checking unused images ...')
		for th in thread_pool:
			th.start()

		for th in thread_pool:
			threading.Thread.join(th)

		# Threads finished
		if len(self.images) == 0:
			message().info('No useless image found, Done!')
			return

		trushDir = os.path.join(self.xcodeproj.projectHome, '__Trushs__')
		if not os.path.isdir:
			os.makedirs(trushDir)

		for n, files in self.images.items():
			for f in files:
				srcFile = os.path.join(self.xcodeproj.projectHome, f['full_path'])
				destFile = os.path.join(trushDir, f['full_path'])
				destDir = os.path.dirname(destFile)
				if not os.path.isdir(destDir):
					os.makedirs(destDir)
				try:
					os.rename(srcFile, destFile)
				except Exception, e:
					message().warning('error while renaming "%s" to "%s": %s' % (srcFile, destFile, e))
				

		message().info('%d useless images resource found, Moving them to %s' % (len(self.images), os.path.basename(trushDir)))
		message().warning('You need to check and remove the file reference from project.pbxproj via Xcode manually')
		message().info('Done!')


	def pendingCheckImages(self):
		self.imagesLock.acquire()
		retDic = dict((k, v) for k, v in self.images.items())
		self.imagesLock.release()
		return retDic

	def markImageBeingUsed(self, imageName):
		if self.images.has_key(imageName):
			self.imagesLock.acquire()
			del self.images[imageName]
			self.imagesLock.release()

	def nextFile(self):
		f = None
		self.fileLock.acquire()
		if len(self.pendingFiles) > 0:
			f = self.pendingFiles[0]
			del self.pendingFiles[0]
		self.fileLock.release()
		return f

	def loadCheckingFiles(self):
		""" load files that need to check if using strings resource """
		self.pendingFiles =[]
		for f in self.xcodeproj.getfiles():
			if f.has_key('lastKnownFileType'):
				if f['lastKnownFileType'][0:11] == 'sourcecode.':
					self.pendingFiles.append({'path':os.path.join(self.xcodeproj.projectHome, f['full_path']), 'type':'sourcecode'})
				elif f['lastKnownFileType'] == 'file.xib':
					self.pendingFiles.append({'path':os.path.join(self.xcodeproj.projectHome, f['full_path']), 'type':'xib'})

			elif os.path.basename(f['path']) == 'InAppSettings.bundle':
				boundlePath = os.path.join(self.xcodeproj.projectHome, f['full_path'])
				for root, dirs, fs in os.walk(boundlePath, True):
					for fileName in fs:
						if os.path.splitext(fileName)[1] == '.plist':
							self.pendingFiles.append({'path':os.path.join(root, fileName), 'type':'plist'})





