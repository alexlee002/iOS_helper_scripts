#!/usr/bin/python
#encoding:utf-8

import os
import sys

from projRes.xc_helper_base import *
from projRes.build_images import *
from projRes.check_files import *
from projRes.check_strings import *
from projRes.build_strings import *
from projRes.check_images import *


def showUsage():
	print 'Usage:\n\t' + os.path.basename(sys.argv[0]) + ' <sub command> <module1 module2 ...> -project <PRJOECT ROOT DIR> [-outlog <xcode|console>]'
	print 'sub command:'
	print '\tbuild\tprecompile project resources.'
	print '\tclean\tclean useless resources'
	print 'modules:'
	print '\tstrings\tlocalized strings resources'
	print '\timages\timage resources'
	print '\tfiles\tonly for clean, clean unused files'
	print '-project PATH\tpath for .xcodeproj'
	print '-outlog STYLE\toutput log style, xcode: used for xcode project compile phases; console: use for command line'


if __name__=="__main__":
	#check args
	modules = []
	action = None
	pendingProject = False
	pendingLog = False
	for arg in sys.argv[1:]:
		if arg in ('build', 'clean'):
			action = arg
		elif action and arg in ('strings', 'images', 'files'):
			modules.append(arg)
		elif arg == '-project':
			pendingProject = True
		elif pendingProject :
			projectPath = arg
			pendingProject = False
		elif arg == '-outlog':
			pendingLog = True
		elif pendingLog :
			if arg == 'xcode':
				message().isXCodeStyle = True
			pendingLog = False
		elif arg in ('-h', '--help', '?'):
			showUsage()
		else:
			message().error('invalid arg:%s' % arg)
			sys.exit(1)

	if not action:
		message().error('invalid command')
		showUsage()
		sys.exit(1)
	if not modules or len(modules) == 0:
		message.error('incomplete command')
		showUsage()
		sys.exit(1)
	if not projectPath or not os.path.isdir(projectPath) or not os.path.splitext(projectPath)[1] == '.xcodeproj':
		message().error('invalid project path, need to specify the ".xcodeproj" path')
		sys.exit(1)

	#####
	xcodeproj = XCProject(projectPath)
	if action == 'build':
		for m in modules:
			if m == 'images':
				message().info('Building images resources ...')
				ImagesBuilder(xcodeproj).buildImagesMacros()
			elif m == 'strings':
				message().info('Building strings resources ...')
				StringsBuilder(xcodeproj).buildStringsMacro()
	if action == 'clean':
		for m in modules:
			if m == 'images':
				message().info('checking  images resources ...')
				ImagesInspector(xcodeproj).checkUselessImages()
			elif m == 'strings':
				message().info('checking  strings resources ...')
				StringsInspector(xcodeproj).checkUselessStrings()
			elif m == 'files':
				message().info('checking  files resources ...')
				FileInspector(xcodeproj).inspectFiles()




	