#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os 
import sys 
import networkx as nx 

from gensim.models import Doc2Vec
import gensim.models.doc2vec
from log_manager.log_config import Logger 
from baselineRunner.BaselineRunner import BaselineRunner
from sklearn.metrics.pairwise import cosine_similarity
import multiprocessing
import joblib
from joblib import Parallel, delayed
import pickle
import numpy as np 
from node2vec.Node2Vec import Node2Vec 
from summaryGenerator.WordBasedGraphGenerator import WordBasedGraphGenerator
from summaryGenerator.PageRankBasedSummarizer import PageRankBasedSummarizer


class Node2VecRunner(BaselineRunner): 

	def __init__(self, *args, **kwargs):
		BaselineRunner.__init__(self, *args, **kwargs)
		self.p2vReprFile = os.environ["P2VECSENTRUNNEROUTFILE"]
		self.n2vReprFile = os.environ["N2VOUTFILE"]
		self.interThr = float(os.environ["GINTERTHR"])
		self.intraThr = float(os.environ["GINTRATHR"])
		self.Graph = nx.Graph()
		self.cores = multiprocessing.cpu_count()
		self.graphFile = os.environ["GRAPHFILE"]
		self.s2vDict = {}
		self.sentenceDict = {}


	def _insertAllNodes(self):
		for result in self.postgresConnection.memoryEfficientSelect(["id"],\
			["sentence"], [], [], []):
			for row_id in range(0,len(result)):
				id_ = result [row_id] [0]
				self.Graph.add_node(id_)
		Logger.logr.info ("Inserted %d nodes in the graph"\
			 %(self.Graph.number_of_nodes()))

	def _insertGraphEdges(self):
		"""
		Process sentences differently for inter and 
		intra documents. 
		"""
		for sentence_id in sentence_id_list:
			for node_id in self.Graph.nodes():
				if node_id != sentence_id:
					
					doc_vec_1 = self.s2vDict[node_id]
					doc_vec_2 = self.s2vDict[sentence_id]
					sim = np.inner(doc_vec_1, doc_vec_2)

					if node_id in sentence_id_list: 
						if sim >= self.intraThr:
							self.Graph.add_edge(sentence_id, node_id, weight=sim)
							#Logger.logr.info("Adding intra edge (%d, %d) with sim=%f" %(sentence_id, node_id, sim))
						
					else:
						if sim >= self.interThr:
							self.Graph.add_edge(sentence_id, node_id, weight=sim)
							#Logger.logr.info("Adding inter edge (%d, %d) with sim=%f" %(sentence_id, node_id, sim))

		#Logger.logr.info('The graph is connected  = %d' %(nx.is_connected(self.Graph)))

	def _iterateOverSentences(self, paragraph_id, sentence_id_list):

		
		for sent_result in self.postgresConnection.memoryEfficientSelect(["sentence_id"],\
			["paragraph_sentence"], [["paragraph_id","=",paragraph_id]], \
			[], ["position"]):
			for row_id in range(0,len(sent_result)):
				self.sentenceDict[sent_result[row_id][0]] = "1"
		
	def _constructSingleDocGraphP2V(self):
		graph = nx.Graph() 
		for node_id in self.sentenceDict.keys():
			for in_node_id in self.sentenceDict.keys():
				if node_id == in_node_id:
					continue 
				else:
					doc_vec_1 = self.s2vDict[node_id]
					doc_vec_2 = self.s2vDict[sentence_id]
					sim = np.inner(doc_vec_1, doc_vec_2)
					if sim > intraThrSummary: 
						graph.add_edge(node_id, in_node_id)
		return graph 

	def _summarizeAndWriteLabels(self):
		wbasedGenerator = WordBasedGraphGenerator (sentDictionary=self.sentenceDict, threshold=self.intraThrSummary)
		nx_G, idMap = wbasedGenerator.generateGraph
		prSummary = PageRankBasedSummarizer(nx_G = nx_G)

		for sumSentID in prSummary.getsummary(self.dumpingFactor):
			print (sumSentID)

		nx_G = _constructSingleDocGraphP2V()
		prSummary = PageRankBasedSummarizer(nx_G = nx_G)
		prSummary.getsummary(self.dumpingFactor)

		for sumSentID in prSummary.getsummary(self.dumpingFactor):
			print (sumSentID)



	def _iterateOverParagraphs(self, doc_id, metadata):
		"""
		Prepare a large graph. Prepare per document graph, 
		summarize and label as train or test.
		"""
		self.sentenceDict.clear()

		for para_result in self.postgresConnection.memoryEfficientSelect(["paragraph_id"],\
			["document_paragraph"], [["document_id","=",doc_id]], \
			[], ["position"]):
			for row_id in range(0, len(para_result)):
				self._iterateOverSentences(para_result[row_id][0])

		for sent_result in self.postgresConnection.memoryEfficientSelect(["id", "content"],\
				["sentence"], [["id", "in", "(%s)"%(",".join(self.sentenceDict.keys()))]], [], []):
			for row_id in range(len(sent_result)):
				self.sentenceDict[sent_result[row_id][0]] = sent_result[row_id][1]


		self._summarizeAndWriteLabels(metadata)
		self._insertGraphEdges()


	def prepareData(self):
		"""
		Loops over documents, then paragraphs, and finally over 
		sentences. select(self, fields = [], tables = [], where = [], 
		groupby = [], orderby = [])
		"""
		self.postgresConnection.connect_database()
		self._insertAllNodes()

		p2vfileToRead = open ("%s.p" %self.p2vReprFile, "rb")
		self.s2vDict = pickle.load(p2vfileToRead)


		# while True: 
		# 	try:
		# 		sent_dict = pickle.load(p2vfileToRead)
		# 		id_ = sent_dict["id"]
		# 		vec = sent_dict["vec"]
		# 		vec = vec / np.linalg.norm(vec)
		# 		self.s2vDict[id_] = vec 
		# 	except Exception as e:
		# 		Logger.logr.info(str(e))
		# 		break 


		for doc_result in self.postgresConnection.memoryEfficientSelect(["id", "metadata"],\
			["document"], [], [], ["id"]):
			for row_id in range(0,len(doc_result)):
				self._iterateOverParagraphs(doc_result[row_id][0], doc_result[row_id][1])
					
		nx.write_gpickle(self.Graph, self.graphFile)
		Logger.logr.info("Total number of edges=%i"%self.Graph.number_of_edges())

		self.postgresConnection.disconnect_database()


	def runTheBaseline(self, latent_space_size):
		"""
		self.dimension = kwargs['dimension'] 
		self.window_size = kwargs['window_size']
		args.cpu_count = kwargs['cpu_count']
		self.outputfile = kwargs['outputfile']
		self.num_walks = kwargs['num_walks']
		self.walk_length = kwargs['walk_length']
		self.p = kwargs['p']
		self.q = kwargs['q']
		"""
		Logger.logr.info("Running Node2vec Internal")
		node2vecInstance = Node2Vec (dimension=latent_space_size, window_size=8,\
			 cpu_count=self.cores, outputfile=self.n2vReprFile,\
			 num_walks=10, walk_length=10, p=4, q=1)
		n2vec = node2vecInstance.get_representation(self.Graph)
		return self.Graph
	
	def runEvaluationTask(self):
		"""
		"""
		

	def prepareStatisticsAndWrite(self):
		"""
		"""
		
