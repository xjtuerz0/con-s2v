#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os 
import sys
import pickle
import numpy as np
from gensim.models import Doc2Vec
import gensim.models.doc2vec
from log_manager.log_config import Logger 
import multiprocessing
from collections import namedtuple
from utility.Utility import Utility
from word2vec.WordDoc2Vec import WordDoc2Vec
from summaryGenerator.SummaryGenerator import SummaryGenerator
from baselineRunner.BaselineRunner import BaselineRunner



label_sent = lambda id_: 'SENT_%s' %(id_)


class P2VSENTCExecutableRunner(BaselineRunner):
	def __init__(self, *args, **kwargs):
		"""
		"""
		BaselineRunner.__init__(self, *args, **kwargs)
		self.postgresConnection.connectDatabase()
		self.latReprName = "p2vsent"
		self.dataDir = os.environ['TRTESTFOLDER']
		self.rootdir = os.environ['SEN2VEC_DIR']
		self.utFunction = Utility("Text Utility")
		self.window_size = str(10)
		self.system_id = 2
		self.sentsFile = os.path.join(self.dataDir, "%s_sents"%self.latReprName)
		self.sentReprFile = os.path.join(self.dataDir, "%s_sentsCEXE_repr"%self.latReprName)
		self.doc2vecOut = os.path.join(self.dataDir,"%s_sentsCEXE_docrepr"%self.latReprName)
	
	def prepareData(self, pd):
		"""
		Query Sentence Data. We dump sentences with their sentence 
		ids. Pre-pad sentences with null word symbol if the number 
		of words in a sentence 
		is less than 9.
		"""
		if pd <= 0: return 0
		sentfiletoWrite = open("%s.txt"%(self.sentsFile),"w")
		for result in self.postgresConnection.memoryEfficientSelect(["id","content"],\
			 ["sentence"], [], [], ["id"]):
			for row_id in range(0,len(result)):
				id_ = result[row_id][0]
				content = gensim.utils.to_unicode(result[row_id][1].strip())
				content = self.utFunction.normalizeText(content, remove_stopwords=0)
				# if len(content) < 9:
				# 	n_nulls = 9 - len(content)
				# 	for n in range(0,n_nulls):
				# 		content.insert(0,"null")
				sentfiletoWrite.write("%s %s%s"%(label_sent(id_),' '.join(content), os.linesep))
			sentfiletoWrite.flush()
		sentfiletoWrite.close()

	def convert_to_str(self, vec):
		str_ = ""
		for val in vec: 
			str_ ="%s %0.3f"%(str_,val)
		return str_

	def runTheBaseline(self, rbase, latent_space_size):
		"""
		We run the para2vec Model and then store sen2vec as pickled 
		dictionaries into the output file. 
		"""
		if rbase <= 0: return 0

		wordDoc2Vec = WordDoc2Vec()
		wPDict = wordDoc2Vec.buildWordDoc2VecParamDict()

		# Run Distributed Memory Version
		wPDict["cbow"], wPDict["sentence-vectors"],wPDict["min-count"] = str(0), str(0), str(0)
		wPDict["train"], wPDict["output"] = "%s.txt"%self.sentsFile, self.doc2vecOut
		wPDict["size"], wPDict["sentence-vectors"] = str(latent_space_size), str(1)
		wPDict["window"] = self.window_size
		args = wordDoc2Vec.buildArgListforW2V(wPDict)
		self._runProcess(args)
		sent2vecModel = Doc2Vec.load_word2vec_format(self.doc2vecOut, binary=False)


		# Run Distributed Bag of Words Version 
		wPDict["cbow"] = str(1)
		wPDict["output"] = "%s_DBOW" % self.doc2vecOut
		args = wordDoc2Vec.buildArgListforW2V(wPDict)
		self._runProcess(args)
		sent2vecModelDBOW = Doc2Vec.load_word2vec_format("%s_DBOW"%self.doc2vecOut, binary=False)
		

		nSent = 0
		for result in self.postgresConnection.memoryEfficientSelect(["count(*)"],\
			['sentence'], [], [], []):
			nSent = int (result[0][0])
		sent2vecFileRaw = open("%s_raw"%(self.sentReprFile),"w") 
		sent2vecFileRaw.write("%s %s%s"%(str(nSent), str(latent_space_size*2), os.linesep))


		sent2vecFile = open("%s.p"%(self.sentReprFile),"wb")
		sent2vec_dict = {}

		sent2vecFile_raw = open("%s_raw.p"%(self.sentReprFile),"wb")
		sent2vec_raw_dict = {}


		for result in self.postgresConnection.memoryEfficientSelect(["id"],\
			 ["sentence"], [], [], ["id"]):
			for row_id in range(0,len(result)):
				id_ = result[row_id][0]	
				vec1 = sent2vecModel[label_sent(id_)]
				vec2 = sent2vecModelDBOW[label_sent(id_)]
				vec = np.hstack((vec1,vec2))
				sent2vec_raw_dict[id_] = vec 
				#Logger.logr.info("Reading a vector of length %s"%vec.shape)
				sent2vecFileRaw.write("%s "%(str(id_)))	
				vec_str = self.convert_to_str(vec)
				#Logger.logr.info(vec_str)
				sent2vecFileRaw.write("%s%s"%(vec_str, os.linesep))
				sent2vec_dict[id_] = vec /  ( np.linalg.norm(vec) +  1e-6)
				

		Logger.logr.info("Total Number of Sentences written=%i", len(sent2vec_dict))			
		pickle.dump(sent2vec_dict, sent2vecFile)	
		pickle.dump(sent2vec_raw_dict, sent2vecFile_raw)	

		sent2vecFile_raw.close()	
		sent2vecFile.close()
	
	def generateSummary(self, gs,  lambda_val=1.0, diversity=False):
		if gs <= 0: return 0
		sent2vecFile = open("%s.p"%(self.sentReprFile),"rb")
		s2vDict = pickle.load (sent2vecFile)

		summGen = SummaryGenerator (diverse_summ=diversity,\
			 postgres_connection = self.postgresConnection,\
			 lambda_val = lambda_val)

		summGen.populateSummary(2, s2vDict)

	def runEvaluationTask(self):
		"""
		Generate Summary sentences for each document. 
		Write sentence id and corresponding metadata 
		into a file. 
		"""
		summaryMethodID = 2

		what_for =""
		try: 
			what_for = os.environ['VALID_FOR'].lower()
		except:
			what_for = os.environ['TEST_FOR'].lower()

		vDict = {}
		if  "rank" in what_for:
			vecFile = open("%s.p"%(self.sentReprFile),"rb")
			vDict = pickle.load(vecFile)
		else:
			vecFile_raw = open("%s_raw.p"%(self.sentReprFile),"rb")
			vDict = pickle.load(vecFile_raw)

		Logger.logr.info ("Performing evaluation for %s"%what_for)
		self.performEvaluation(summaryMethodID, self.latReprName, vDict)

	
	def doHouseKeeping(self):
		"""
		Here, we destroy the database connection.
		"""
		self.postgresConnection.disconnectDatabase()