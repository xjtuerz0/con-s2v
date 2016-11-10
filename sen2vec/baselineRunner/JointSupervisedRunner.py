#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os 
import sys 
import networkx as nx 
from gensim.models import Word2Vec
from log_manager.log_config import Logger 
from gensim.models import Doc2Vec
from baselineRunner.BaselineRunner import BaselineRunner
import pickle
import math 
import operator 
import multiprocessing 
import subprocess 
import numpy as np 
from word2vec.WordDoc2Vec import WordDoc2Vec
from summaryGenerator.SummaryGenerator import SummaryGenerator


label_sent = lambda id_: 'SENT_%s' %(id_)


class JointSupervisedRunner(BaselineRunner): 

	def __init__(self, *args, **kwargs):
		BaselineRunner.__init__(self, *args, **kwargs)
		self.jointSupReprFile = os.environ["SJOINTS2VRPRFILE"]
		self.dataDir = os.environ['TRTESTFOLDER']
		self.sentsFile = os.environ['P2VCEXECSENTFILE']
		self.num_walks = int(os.environ["NUM_WALKS"])
		self.walk_length = int(os.environ["WALK_LENGTH"])
		self.jointbeta= float(os.environ['JOINT_SENT_BETA'])
		self.jointbetaLab = float(os.environ['JOINT_SENT_LBETA'])
		self.cores = multiprocessing.cpu_count()
		self.latReprName = "joint_lab_s2v"

		self.postgresConnection.connectDatabase()
	

	def prepareNeighborData(self):

		walkinputFile = open(os.path.join(self.dataDir, "node2vecwalk.txt"))
		joint_nbr_file  = open(os.path.join(self.dataDir,"%s_nbr"%(self.latReprName)), "w")

		line_count = 0 
		for line in walkinputFile: 
			line_count = line_count + 1 

		joint_nbr_file.write("%s %s %s"%(str(line_count),str(self.num_walks),str(self.walk_length)))
		joint_nbr_file.write(os.linesep)

		walkinputFile = open(os.path.join(self.dataDir, "node2vecwalk.txt")) # reset position 
		for line in walkinputFile:
			line_elems = line.strip().split(" ")

			for pos in range(0, self.walk_length+1):
				if pos >= len(line_elems):
					joint_nbr_file.write("-1 ")
				else:
					joint_nbr_file.write("%s "%label_sent(line_elems[pos]))

			joint_nbr_file.write(os.linesep)
			joint_nbr_file.flush()
		joint_nbr_file.close()

	def prepareData(self, pd):
		if pd <= 0: return 0 
		self.prepareNeighborData()
		summaryMethodID = 2 
		topics = []
		nSent = 0 
		labelFile = open(os.path.join(self.dataDir, "%s_label"%self.latReprName), "w")

		# Number of sentences 
		for result in self.postgresConnection.memoryEfficientSelect(["count(*)"],\
			["sentence,summary"], [["sentence.id", "=", "summary.sentence_id"],\
			 	["summary.method_id", "=", summaryMethodID], ['sentence.istrain','=',"'YES'"]\
			 	 ], [], []):
			nSent = int (result[0][0])

		# Number of topics 
		for result in self.postgresConnection.memoryEfficientSelect(["distinct(topic)"],\
			['sentence'], [], [], []):
			for nrows in range(0,len(result)):
				topics.append(result[nrows][0])
		ntopics = len(topics)
		print(topics)

		labelFile.write("%i %i%s"%(nSent, ntopics, os.linesep))

		# Prepare Label Data 
		for result in self.postgresConnection.memoryEfficientSelect(["sentence.id","sentence.topic"],\
			 ["sentence,summary"], [["sentence.id", "=", "summary.sentence_id"],\
			 	["summary.method_id", "=", summaryMethodID], ['sentence.istrain','=',"'YES'"]\
			 	 ], [], []):
				for nrows in range(0, len(result)):
					id_ = result[nrows][0]
					topic_id = topics.index(result[nrows][1])
					labelFile.write("%s %i%s"%(label_sent(id_), topic_id, os.linesep))
					labelFile.flush()

		labelFile.close()


	def convert_to_str(self, vec):
		str_ = ""
		for val in vec: 
			str_ ="%s %0.3f"%(str_,val)
		return str_


	def runTheBaseline(self, rbase, latent_space_size):
		"""
		Should we also optimize for window size?
		"""
		if rbase <= 0: return 0 


		wordDoc2Vec = WordDoc2Vec()
		wPDict = wordDoc2Vec.buildWordDoc2VecParamDict()
		wPDict["cbow"] = str(0) 
		wPDict["output"] = os.path.join(self.dataDir , "%s_raw_DBOW"%self.latReprName)
		wPDict["sentence-vectors"] = str(1)
		wPDict["min-count"] = str(0)
		wPDict["train"] = "%s.txt"%self.sentsFile
		wPDict["beta"] = str(self.jointbeta)
		wPDict["label-beta"] = str(self.jointbetaLab) 
		
		wPDict["size"]= str(latent_space_size)
		args = []
		neighborFile = os.path.join(self.dataDir,"%s_nbr"%(self.latReprName))
		wPDict["neighborFile"] = neighborFile
		labelFile = os.path.join(self.dataDir, "%s_label"%self.latReprName)
		wPDict["label"] = labelFile 


		args = wordDoc2Vec.buildArgListforW2VWith_LAB_Neighbors(wPDict, 4)
		self._runProcess(args)
		jointvecModel = Doc2Vec.load_word2vec_format(wPDict["output"], binary=False)


		wPDict["cbow"] = str(1) 
		wPDict["output"] = os.path.join(self.dataDir,"%s_raw_DM"%self.latReprName)
		args = wordDoc2Vec.buildArgListforW2VWith_LAB_Neighbors(wPDict, 4)
		self._runProcess(args)
		jointvecModelDM = Doc2Vec.load_word2vec_format(wPDict["output"], binary=False)	

		jointvecFile = open("%s.p"%(self.jointSupReprFile),"wb")
		jointvec_dict = {}

		jointvecFile_raw = open("%s_raw.p"%(self.jointSupReprFile),"wb")
		jointvec_raw_dict = {}

		for result in self.postgresConnection.memoryEfficientSelect(["id"],\
			 ["sentence"], [], [], ["id"]):
			for row_id in range(0,len(result)):
				id_ = result[row_id][0]	
				vec1 = jointvecModel[label_sent(id_)]
				vec2 = jointvecModelDM[label_sent(id_)]
				vec = np.hstack((vec1,vec2))
				jointvec_raw_dict[id_] = vec 		
				jointvec_dict[id_] = vec /  ( np.linalg.norm(vec) +  1e-6)
				
		Logger.logr.info("Total Number of Sentences written=%i", len(jointvec_raw_dict))			
		pickle.dump(jointvec_dict, jointvecFile)	
		pickle.dump(jointvec_raw_dict, jointvecFile_raw)	

		jointvecFile_raw.close()	
		jointvecFile.close()

	def generateSummary(self, gs, methodId, filePrefix,\
		 lambda_val=1.0, diversity=False):
		if gs <= 0: return 0
		jointvecFile = open("%s.p"%(self.jointReprFile),"rb")
		j2vDict = pickle.load (jointvecFile)

		summGen = SummaryGenerator (diverse_summ=diversity,\
			 postgres_connection = self.postgresConnection,\
			 lambda_val = lambda_val)

		# Need a method id for the joint 
	
	def runEvaluationTask(self):
		summaryMethodID = 2 
		jointvecFile_raw = open("%s_raw.p"%(self.jointSupReprFile),"rb")
		js2vDict_raw = pickle.load(jointvecFile_raw)

		if os.environ['EVAL']=='VALID' and os.environ['VALID_FOR']=='CLASS':
			self._runClassificationValidation(summaryMethodID,"%s_raw"%self.latReprName, js2vDict_raw)
		elif os.environ['EVAL']=='VALID' and os.environ['VALID_FOR']=='CLUST':
			self._runClusteringValidation(summaryMethodID,"%s_raw"%self.latReprName, js2vDict_raw)
		elif os.environ['EVAL']=='TEST' and os.environ['TEST_FOR']=='CLASS':	
			self._runClassification(summaryMethodID,"%s_raw"%self.latReprName, js2vDict_raw)
		else:
			self._runClustering(summaryMethodID,"%s_raw"%self.latReprName, js2vDict_raw)
		
	def doHouseKeeping(self):
		"""
		Here, we destroy the database connection.
		"""
		self.postgresConnection.disconnectDatabase()