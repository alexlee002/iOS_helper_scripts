#!/usr/bin/python
#encoding:utf-8
#Filename: xc_helper_base.py


import os
import sys
import subprocess
import json
import re
import StringIO
import math
import shutil
import time
from collections import OrderedDict
from hashlib import md5


# 用装饰器实现单例
def singleton(cls, *args, **kw):
	instances = {}
	def _singleton():
		if cls not in instances:
			instances[cls] = cls(*args, **kw)
		return instances[cls]
	return _singleton

@singleton
class message(object):
	"""a better way to show outputs"""

	isXCodeStyle = False

	def info(self, message):
		print message

	def warning(self, message):
		if self.isXCodeStyle:
			print 'warning: %s' % message
		else:
			print '\033[33m%s\033[0m' % message

	def error(self, message):
		if self.isXCodeStyle:
			print 'error: %s' % message
		else:
			print '\033[1;31m%s\033[0m' % message


#####################################################################################################################
def trimComment(filePath):
	trimCommentShell = os.path.normpath(os.path.abspath(os.path.join(os.path.join(os.path.dirname(__file__), '..'), 'trimComment.sh')))
	if not os.path.isfile(trimCommentShell):
		message().error('File "%s" not exists!' % trimCommentShell)
		sys.exit(1)
	p = subprocess.Popen([trimCommentShell, filePath], stdout=subprocess.PIPE)
	stdout, stderr = p.communicate()
	if p.returncode != 0:
		message().error('Fail to trim comments, file: "%s"' % f['path'])
		message().info(stderr)
	return stdout


#####################################################################################################################

class XCProject(object):
	def __init__(self, project_path):
		super(XCProject, self).__init__()
		project_path = os.path.normpath(os.path.abspath(project_path))
		isValid = os.path.isdir(project_path) and os.path.splitext(project_path)[1] == '.xcodeproj'
		if not isValid:
			message().error('"%s" is not a valid xcode project' % project_path)
			sys.exit(1)

		self.projectHome = os.path.dirname(project_path)
		p = subprocess.Popen(['/usr/bin/plutil', '-convert', 'json', '-o', '-', os.path.join(project_path, 'project.pbxproj')], stdout=subprocess.PIPE)
		stdout, stderr = p.communicate()
		if p.returncode != 0:
			message().error('Can not parse project file')
			message().info(stdout)
			sys.exit(1)

		self.json = json.loads(stdout)
		self.rootObjectID = str(self.objectWithKeyPath(['rootObject']))
		mainGroupPath = self.objectWithKeyPath(['objects', self.rootObjectID, 'projectDirPath'])
		if mainGroupPath == None:
			mainGroupPath = ''
		self.completeObjectsPath(str(self.objectWithKeyPath(['objects', self.rootObjectID, 'mainGroup'])), mainGroupPath)


	def getfiles(self, args={'sourceTree':'<group>'}):
		files = [o for o in self.json['objects'].values() if o['isa'] == 'PBXFileReference']
		def checkObject(o):
			for k in args.keys():
				matches = o.has_key(k) and o[k] == args[k]
				if not matches:
					return False
			return True
					
		return filter(checkObject, files)


	def productName(self):
		targets = self.objectWithKeyPath(['objects', self.rootObjectID, 'targets'])
		for target in targets:
			if self.objectWithKeyPath(['objects', self.rootObjectID, 'attributes', 'TargetAttributes', str(target)]):
				return str(self.objectWithKeyPath(['objects', str(target), 'productName']))
		return None

	def projectClassPrefix(self):
		projPrefix = self.objectWithKeyPath(['objects', self.rootObjectID, 'attributes', 'CLASSPREFIX'])
		if not projPrefix:
			projPrefix = 'MYAPP'
		return projPrefix.upper()



	def completeObjectsPath(self, parentID, parentPath, groups=''):
		parent = self.objectWithKeyPath(['objects', parentID])
		if parent.has_key('path'):
			if parent.has_key('sourceTree') and parent['sourceTree'] == '<group>':
				parentPath = os.path.normpath(os.path.join(parentPath, parent['path']))
			elif parent.has_key('sourceTree') and parent['sourceTree'] == 'SOURCE_ROOT':
				parentPath = parent['path']
		parent['full_path'] = parentPath

		if parent.has_key('isa') and parent['isa'] == 'PBXGroup':
			if parent.has_key('path'):
				groups = os.path.normpath(os.path.join(groups, parent['path']))
			elif parent.has_key('name'):
				groups = os.path.normpath(os.path.join(groups, parent['name']))

		parent['groups'] = groups
		if parent.has_key('children'):
			for childID in parent['children']:
				self.completeObjectsPath(str(childID), parentPath, groups)

	def objectWithKeyPath(self, path=[], o=None):
		if o == None:
			o = self.json

		for p in path:
			if o.has_key(p):
				o = o[p]
			else:
				return None
		return o


		
		
#####################################################################################################################

class StringObject(object):
	XCStringsDefaultState = 0
	XCStringsUnusedState = -1
	XCStringsUnTranslatedState = 1
	def __init__(self, lang, name, text, state):
		super(StringObject, self).__init__()
		self.lang = lang
		self.name = name
		self.text = text
		self.state = state

#####################################################################################################################		

class StringResource(object):
	
	def __init__(self, xcodeproj):
		super(StringResource, self).__init__()
		self.xcodeproj = xcodeproj

		self.knownRegions = self.xcodeproj.objectWithKeyPath(['objects', self.xcodeproj.rootObjectID, 'knownRegions'])
	

	def loadConfig(self, stringTable='Localizable.strings'):
		stringsFiles = {}
		for f in self.xcodeproj.getfiles({'sourceTree':'<group>', 'lastKnownFileType':'text.plist.strings'}):
			path = str(self.xcodeproj.objectWithKeyPath(['full_path'], f))
			if not os.path.basename(path) == stringTable:
				continue

			name = self.xcodeproj.objectWithKeyPath(['name'], f)
			if name == None:
				path = self.xcodeproj.objectWithKeyPath(['path'], f)
				if not path == None:
					name = os.path.basename(os.path.dirname(path)).splitext()[0]
			stringsFiles[name] = path

		self.stringsFiles = stringsFiles
		return self

	def loadStrings(self, lang='en', doCheck=True):
		if not lang in self.stringsFiles.keys():
			message().error('Not found language in project: "%s"' % lang)
			sys.exit(1)

		stringsFile = os.path.join(self.xcodeproj.projectHome, self.stringsFiles[lang])
		if not os.path.isfile(stringsFile):
			message().error('File "%s" not exists!' % stringsFile)
			sys.exit(1)

		fileContent = trimComment(stringsFile)
		strings = OrderedDict()
		duplicatedStrings = {}
		lines = StringIO.StringIO(fileContent).readlines()
		pattern = re.compile("^\s*\"(.+)\"\s*=\s*\"(.*)\"\s*;")
		for l in lines:
			matches = pattern.search(l)
			if matches:
				name = matches.group(1)
				text = matches.group(2)
				strObj = StringObject(lang, name, text, StringObject.XCStringsDefaultState)
				if strings.has_key(name) and not text == strings[name].text:
					if duplicatedStrings.has_key(name):
						duplicatedStrings[name].append(text)
					else:
						duplicatedStrings[name] = [strings[name].text, text]
				strings[name] = strObj

		if doCheck and len(duplicatedStrings) > 0:
			errmsg = 'Duplicated strings resources found in strings file: %s' % self.stringsFiles[lang]
			for name in duplicatedStrings.keys():
				errmsg = errmsg + '\n' + '\n'.join(['\t"%s"\t= "%s";' % (name, t) for t in duplicatedStrings[name]]) + '\n'
			message().error(errmsg)
			sys.exit(1)

		return strings

	def saveToFile(self, lang, strings, isDefaultLang=False):
		if not lang in self.stringsFiles.keys():
			message().error('Not found language in project: "%s"' % lang)
			sys.exit(1)

		stringsFile = os.path.join(self.xcodeproj.projectHome, self.stringsFiles[lang])
		#make a backup copy
		bakupFile = stringsFile + '.bak'
		try:
			shutil.copyfile(stringsFile, bakupFile)
		except Exception, e:
			message().warning('Can make backup file:%s, error:%s' % (bakupFile, e))

		#default language file, we need to keep the original order and comments
		if isDefaultLang:
			pattern = re.compile("^\s*\"(.+)\"\s*=\s*\"(.*)\"\s*;")
			fp = open(stringsFile, 'rb')
			lines = fp.readlines()
			fp.close()

			newLines = []
			for l in lines:
				matches = pattern.search(l)
				if matches:
					name = matches.group(1)
					if strings.has_key(name):
						strobj = strings[name]
						if not strobj.state == StringObject.XCStringsUnusedState:
							newLines.append(self.prettyFormatStrings(strobj.name, strobj.text))
				else:
					newLines.append(l)

			writer = open(stringsFile, 'w')
			if not writer:
				message().error('Can not write to file: %s' % stringsFile)
				sys.exit(1)

			writer.write(''.join(['%s' % l for l in newLines]))
			writer.close()

			self.updateStringsVersion(lang, self.stringsHash(strings))

		else:
			writer = open(stringsFile, 'w')
			if not writer:
				message().error('Can not write to file: %s' % stringsFile)
				sys.exit(1)
		
			try:
				writer.write('///\n')
				writer.write('/// %s\n' % os.path.basename(stringsFile))
				writer.write('/// %s\n' % self.xcodeproj.productName())
				writer.write('///\n')
				now = long(time.time())
				timeArray = time.localtime(now)
				writer.write('/// Modified by xc_helper_script at %s\n' % time.strftime("%Y-%m-%d", timeArray))
				writer.write('/// Copyright (c) 2012-%s %s. All rights reserved.\n' % (time.strftime("%Y", timeArray), self.xcodeproj.objectWithKeyPath(['objects', self.xcodeproj.rootObjectID, 'attributes', 'ORGANIZATIONNAME'])))
				writer.write('///\n')
				writer.write('/// Language: %s\n' % lang)
				writer.write('/// VERSION: %s\n' % self.stringsHash(strings))
				writer.write('///\n\n\n')

				for name, obj in strings.items():
					if not obj.state == StringObject.XCStringsUnusedState:	
						writer.write(self.prettyFormatStrings(obj.name, obj.text))
			except Exception, e:
				message().warning('Exception occured while saving file: %s, error: %s;\nRestore as backup file.' % (stringsFile, e))
				try:
					shutil.copyfile(bakupFile, stringsFile)
				except Exception, e:
					message().error('Failed to restore backup file: %s, error:%s' % (stringsFile, e))
					sys.exit(1)
			finally:
				writer.close()

		os.remove(bakupFile)

	def prettyFormatStrings(self, strName, strVal):
		tabNum = int(math.floor(max(0, 40 - len(strName) -2) / 4))
		tabsSpace = ' '.join('\t' for n in range(tabNum))
		return '"%s" %s= "%s";\n' % (strName, tabsSpace, strVal)
		

	def updateStringsVersion(self, lang, newVer):
		stringsFile = os.path.join(self.xcodeproj.projectHome, self.stringsFiles[lang])
		fp = open(stringsFile, 'rb')
		lines = fp.readlines()
		fp.close()

		foundVersion = False
		fp = open(stringsFile, 'wb')
		for l in lines:
			matches = re.search(ur"^///\s*VERSION:\s*([0-9a-zA-Z]{32})", l)
			if matches:
				foundVersion = True
				fp.write('/// VERSION: %s\n' % newVer)
			else:
				fp.write('%s' % l)
		if not foundVersion:
			fp.write('\n\n/// VERSION: %s\n' % newVer)
		fp.close()


	def stringsHash(self, strings):
		if not strings:
			return None

		content = '\n'.join(['"%s"="%s";' % (k, v.text) for k, v in strings.items()])
		m = md5()
		m.update(content)
		return m.hexdigest()


#####################################################################################################################
class ImagesResource(object):
	""" images resource base operations """
	def __init__(self, xcodeproj):
		super(ImagesResource, self).__init__()
		self.xcodeproj = xcodeproj

	def loadImagesResource(self, ignoreGroupPaths=('External_Libraries_and_Frameworks')):
		imageResources = {}
		duplicatedImages = {}
		for f in [f for f in self.xcodeproj.getfiles() if str(self.xcodeproj.objectWithKeyPath(['lastKnownFileType'], f))[0:6] == 'image.']:
			shouldIgnore = False
			for ig in ignoreGroupPaths:
				if self.isParentFolder(ig, f['groups']):
					shouldIgnore = True
					break
			if shouldIgnore:
				message().warning('Ignore file:%s' % f['full_path'])
				continue

			imgName = self.imageNameFromPath(os.path.basename(f['path'])).lower()
			if imageResources.has_key(imgName) and os.path.basename(f['path']).lower() in [os.path.basename(fn['path']).lower() for fn in imageResources[imgName]]:
				if not duplicatedImages.has_key(imgName):
					duplicatedImages[imgName] = []
				duplicatedImages[imgName].append(f['full_path'])
			else:
				if not imageResources.has_key(imgName):
					imageResources[imgName] = []
				imageResources[imgName].append(f)

		if len(duplicatedImages) > 0:
			errmsg = 'Duplicated image names found:'
			for name in duplicatedImages.keys():
				errmsg = errmsg + '\n' + '\n'.join(['%s' % t for t in duplicatedImages[name]]) + '\n'
			message().error(errmsg)
			sys.exit(1)

		notFoundImages = []
		for arr in imageResources.values():
			for f in arr:
				imagepath = os.path.join(self.xcodeproj.projectHome, f['full_path'])
				if not os.path.isfile(imagepath):
					notFoundImages.append(f['full_path'])
		if len(notFoundImages) > 0:
			errmsg = 'Image files not found:\n' + '\n'.join('%s' % f for f in notFoundImages) + '\n'
			message().error(errmsg)
			sys.exit(1)


		return imageResources
				



	def imageNameFromPath(self, path):
		name = ''
		for component in path.split('.'):
			if len(name.strip()) == 0:
				name = component
				pos = name.find('@')

				if pos >= 0:
					name = name[0: pos]

				pos = name.find('~')
				if pos >= 0:
					name = name[0: pos]

		return name

	def isParentFolder(self, parent, child):
		if not parent or not child:
			return False

		parent = os.path.normpath(parent)
		child = os.path.normpath(child)

		if parent == child:
			return True

		if len(parent) < len(child):
			parent = parent + '/'
			if child[0:len(parent)] == parent:
				return True

		return False







