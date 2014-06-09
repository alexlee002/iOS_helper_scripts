#!/usr/bin/python
#encoding:utf-8
#Filename: build_strings.py

import os
import sys
import re
from xc_helper_base import XCProject
from xc_helper_base import StringResource
from xc_helper_base import StringObject
from xc_helper_base import message
from collections import OrderedDict

import time

class StringsBuilder(object):
	""" Build macros for strings """
	def __init__(self, xcodeproj):
		super(StringsBuilder, self).__init__()
		self.xcodeproj = xcodeproj
		self.strings = StringResource(xcodeproj).loadConfig()

	def buildStringsMacro(self, lang='en'):
		projPrefix = self.xcodeproj.projectClassPrefix()
		genFileName = projPrefix.upper() + 'LocalizedStrings'
		autoGenDir = os.path.join(self.xcodeproj.projectHome, 'autoGen')
		if not os.path.isdir(autoGenDir):
			os.makedirs(autoGenDir)

		if not os.path.isdir(autoGenDir):
			message().error('Failed to create directory: "%s"' % autoGenDir)
			sys.exit(1)

		headerFile = os.path.join(autoGenDir, genFileName) + '.h'
		sourceFile = os.path.join(autoGenDir, genFileName) + '.m'

		needRebuild = False
		if not os.path.isfile(headerFile) or not os.path.isfile(sourceFile):
			needRebuild = True

		versionChanged = False
		currentHash = self.strings.stringsHash(self.strings.loadStrings(lang))
		if not currentHash:
			message().error('Failed to caculator strings hash')
			sys.exit(1)

		macrosFileHash = self.macrosFileVersion(headerFile)
		if not macrosFileHash or not currentHash.lower() == macrosFileHash.lower():
			versionChanged = True


		if not needRebuild and not versionChanged:
			message().info('No change, Done!')
			return

		headerFP = open(headerFile, 'wb')
		sourceFP = open(sourceFile, 'wb')

		self.writeFileHeader(genFileName + '.h', currentHash, headerFP)
		self.writeFileHeader(genFileName + '.m', currentHash, sourceFP)

		autoGenMethodName = projPrefix.upper()+'LocalizedString'
		headerFP.write('NSString * ' + autoGenMethodName + '(NSString *strKey);\n\n')
		sourceFP.write('#import "' + genFileName + '.h"\n\n')
		self.genLocalizedSringMethod(autoGenMethodName, sourceFP)

		strings = self.strings.loadStrings(lang, True)
		for k, v in strings.items():
			if not v.state == StringObject.XCStringsUnusedState:
				name = v.name.strip()
				varName = 'k%sStr%s' % (projPrefix.upper(), name.title())
				headerFP.write('#define %s %s\n' % (self.macroNameForString(name), '%s(%s)' % (autoGenMethodName, varName)))
				headerFP.write('extern NSString * const %s; \n\n' % varName)

				sourceFP.write('NSString * const %s\t= "%s";\n' % (varName, name))

		headerFP.close()
		sourceFP.close()

		self.strings.updateStringsVersion(lang, self.strings.stringsHash(strings))
		message().info('Done!')


	def macroNameForString(self, strName):
		name = strName.strip()
		p = re.compile('([^a-zA-Z0-9_])')
		p.sub('_', name)
		return '%sSTR_%s' % (self.xcodeproj.projectClassPrefix(), name.upper())

	def macrosFileVersion(self, macrosFile):
		if not os.path.isfile(macrosFile):
			return None

		fp = open(macrosFile, 'rb')
		if not fp:
			message().warning('Can not open file: %s' % macrosFile)
			return None

		version = None
		while True:
			lines = fp.readlines(100)
			if not lines:
				break
			for l in lines:
				matches = re.search(ur"^///\s*VERSION:\s*([0-9a-zA-Z]{32})", l)
				if matches:
					version = matches.group(1)
					break
		fp.close()
		return version


	def writeFileHeader(self, fileName, version, fp):
		file_header_commet =  '///\n/// %s\n///\n' % fileName
		file_header_commet += '/// %s\n\n' % self.xcodeproj.productName()
		file_header_commet += '/// This file is autogenerated via scripts\n'
		file_header_commet += '/// Generates strings key macros\n'
		file_header_commet += '///\n'
		now = long(time.time())
		timeArray = time.localtime(now)
		file_header_commet += '/// Modified by xc_helper_script at %s\n' % time.strftime("%Y-%m-%d", timeArray)
		file_header_commet += '/// Copyright (c) 2012-%s %s. All rights reserved.\n' % (time.strftime("%Y", timeArray), self.xcodeproj.objectWithKeyPath(['objects', self.xcodeproj.rootObjectID, 'attributes', 'ORGANIZATIONNAME']))
		file_header_commet += '/// VERSION:%s\n' % version
		file_header_commet += '///\n\n\n\n'
		fp.write(file_header_commet)

	def genLocalizedSringMethod(self, methodName, fp):
		src_fun  = 'NSString* ' + methodName + '(NSString *strKey) {\n'
		src_fun += '    static NSString *VAL_NOT_FOUND = @"__VAL_NOT_FOUND__";\n'
		src_fun += '    NSString *localizedString = [[NSBundle mainBundle] localizedStringForKey:strKey value:VAL_NOT_FOUND table:nil];\n'
		src_fun += '    if ([localizedString isEqualToString:VAL_NOT_FOUND]) {\n'
		src_fun += '        if (![[[NSLocale preferredLanguages] objectAtIndex:0] isEqualToString:@"en"]) {\n'
		src_fun += '            static NSBundle *EN_LANG_BUNDLE = nil;\n'
		src_fun += '            if (EN_LANG_BUNDLE == nil) {\n'
		src_fun += '                NSString *path = [[NSBundle mainBundle] pathForResource:@"en" ofType:@"lproj"];\n'
		src_fun += '#if ! __has_feature(objc_arc)\n'
		src_fun += '                EN_LANG_BUNDLE = [[NSBundle bundleWithPath:path] retain];\n'
		src_fun += '#else\n'
		src_fun += '                EN_LANG_BUNDLE = [NSBundle bundleWithPath:path];\n'
		src_fun += '#endif\n'
		src_fun += '            }\n'
		src_fun += '            localizedString = [EN_LANG_BUNDLE localizedStringForKey:strKey value:@"" table:nil];\n'
		src_fun += '        } else {\n'
		src_fun += '            localizedString = @"";\n'
		src_fun += '        }\n'
		src_fun += '    }\n'
		src_fun += '    return localizedString;\n'
		src_fun += '}\n\n\n'
		fp.write(src_fun)



		