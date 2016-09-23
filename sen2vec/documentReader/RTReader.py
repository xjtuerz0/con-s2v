#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os 
import logging 
from documentReader.DocumentReader import DocumentReader
from documentReader.PostgresDataRecorder   import PostgresDataRecorder
from log_manager.log_config import Logger
import re


class RTReader(DocumentReader):
	""" 
	RottenTomato Document Reader. Reads RottenTomato documents extracted from 
	: 
	"""

	def __init__(self,*args, **kwargs):
		"""
		Initialization assumes that RT_PATH environment is set. 
		To set in linux or mac: export RT_PATH=/some_directory_containing_RottenTomato_data
		"""
		DocumentReader.__init__(self, *args, **kwargs)
		self.dbstring = os.environ["RT_DBSTRING"]
		self.postgres_recorder = PostgresDataRecorder(self.dbstring)
		self.folderPath = os.environ['RT_PATH']
	
	def readTopic(self):
		"""
		"""
		rootDir = "%s/train" %self.folderPath
		return self._getTopics(rootDir)
	
	def readDocument(self, ld): 
		"""
		"""
		if ld <= 0: return 0 	
		self.postgres_recorder.trucateTables()
		self.postgres_recorder.alterSequences()
		topic_names = self.readTopic()
		
		
		document_id = 0
		for first_level_folder in next(os.walk(self.folderPath))[1]:
			if not(DocumentReader._folderISHidden(self, first_level_folder)):
				for topic in topic_names:
					for file_ in os.listdir("%s%s%s%s%s" %(self.folderPath, "/", \
											first_level_folder, "/", topic)):
						file_content = self._getTextFromFile("%s%s%s%s%s%s%s" \
							%(self.folderPath, "/", first_level_folder, "/", topic, "/", file_))
						
						file_content = file_content.split("%s" %os.linesep)
						for doc_content in file_content:
							document_id += 1
							title, metadata, istrain = None, None, None					
							try:
								trainortest = first_level_folder
								metadata = "SPLIT:%s"%trainortest
								istrain = 'Yes' if trainortest.lower() == 'train' else 'NO'			
							except:
								Logger.logr.info("NO MetaData or Train Test Tag")
							self.postgres_recorder.insertIntoDocTable(document_id, title, \
										doc_content, file_, metadata) 
							category = topic.split('.')[0]
							self.postgres_recorder.insertIntoDocTopTable(document_id, \
										[topic], [category]) 		
							self._recordParagraphAndSentence(document_id, doc_content, self.postgres_recorder, topic, istrain)
					
					
		Logger.logr.info("Document reading complete.")
		return 1
	
	
	def runBaselines(self):
		"""
		"""
		pass
