import os
import sys

from xc_helper_base import XCProject
from xc_helper_base import message


class FileInspector(object):
	"""docstring for fileInspector"""
	def __init__(self, xcodeproj):
		super(FileInspector, self).__init__()
		self.xcodeproj = xcodeproj
		self.loadFiles()


	def loadFiles(self):
		self.paths = []
		self.files = []
		for f in self.xcodeproj.getfiles(args={}):
			if f.has_key('sourceTree') and not f['sourceTree'] in ('<group>', 'SOURCE_ROOT'):
				continue

			if not f['full_path'] in self.files:
				self.files.append(f['full_path'])
			if f.has_key('lastKnownFileType') and (f['lastKnownFileType'] == 'folder' or f['lastKnownFileType'][0:7] == 'folder.'):
				continue
			if f.has_key('lastKnownFileType') and f['lastKnownFileType'] in ('wrapper.framework', 'wrapper.plug-in'):
				continue
			if f['path'][0:5] == 'Pods/':
				continue

			path = os.path.dirname(f['full_path'])
			if not path in self.paths:
				self.paths.append(path)

		self.paths.sort(key=lambda x: len(self.componentsOfPath(x)), reverse=True)


	def inspectFiles(self):
		''' Check if files are included in project.pbxproj '''
		uselessFiles = []
		for p in self.paths:
			abspath = os.path.join(self.xcodeproj.projectHome, p)
			if not os.path.exists(abspath):
				message().error('"%s" not exists!' % p)
				continue

			for obj in os.listdir(abspath):
				obj = os.path.join(p, obj)
				if not obj in self.files and not self.containsCommonPath(self.paths, obj):
					uselessFiles.append(obj)

		if len(uselessFiles) == 0:
			message().info('No unincluded files found. Done!')
			return

		trushDir = os.path.join(self.xcodeproj.projectHome, '__Trushs__')
		if not os.path.isdir:
			os.makedirs(trushDir)

		for f in uselessFiles:
			srcFile = os.path.join(self.xcodeproj.projectHome, f)
			destFile = os.path.join(trushDir, f)
			destDir = os.path.dirname(destFile)
			if not os.path.isdir(destDir):
				os.makedirs(destDir)
			try:
				os.renames(srcFile, destFile)
			except Exception, e:
				message().warning('error while renaming "%s" to "%s": %s' % (srcFile, destFile, e))

		message().info('%d unincluded files found, Moving them to %s' % (len(uselessFiles), os.path.basename(trushDir)))
		message().info('Done!')



	def containsCommonPath(self, paths, path):
		if not paths or not path:
			return False

		for p in paths:
			if os.path.commonprefix((p, path)) == path:
				return True
		return False

	def componentsOfPath(self, path):
		components = []
		drver, fpath = os.path.splitdrive(path)
		if drver:
			components.append(drver)

		for p in fpath.split(os.sep):
			components.append(p)

		return components

		