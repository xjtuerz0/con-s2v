#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os 
import sys 
import networkx as nx 
from gensim.models import Word2Vec
from log_manager.log_config import Logger 
from baselineRunner.BaselineRunner import BaselineRunner
import pickle
import math 
import operator 
import multiprocessing 
import subprocess 
import numpy as np 
import gensim 
from utility.Utility import Utility
from word2vec.WordDoc2Vec import WordDoc2Vec
from summaryGenerator.SummaryGenerator import SummaryGenerator
import scipy.stats

label_sent = lambda id_: 'SENT_%s' %(id_)


class RegularizedSen2VecRunner(BaselineRunner): 

    def __init__(self, *args, **kwargs):
        BaselineRunner.__init__(self, *args, **kwargs)
        self.dataDir = os.environ['TRTESTFOLDER']
        self.latReprName = "reg_s2v"
        self.regsen2vReprFile = os.path.join(self.dataDir, "%s_repr"%self.latReprName)
        self.sentsFile = os.path.join(self.dataDir, "%s_sents"%self.latReprName)
        self.regBetaUNW = 0.3
        self.regBetaW = 0.3
        self.Graph = nx.Graph()
        self.window_size = str(10)
        self.cores = multiprocessing.cpu_count()
        self.graphFile = os.path.join(self.dataDir, \
                "%s_graph_%s_%s"%(os.environ['DATASET'], os.environ['GINTERTHR'],\
                    os.environ['GINTRATHR']))
        self.postgresConnection.connectDatabase()
        self.rootdir = os.environ['SEN2VEC_DIR']
        self.utFunction = Utility("Text Utility")
        self.system_id = 6
    
    def __getMaxNeighbors(self):
        """
        Calculates the maximum number of neighbors.
        """
        max_neighbor = 0 
        for nodes in self.Graph.nodes():
            nbrs = self.Graph.neighbors(nodes)
            if len(nbrs) > max_neighbor:
                max_neighbor = len(nbrs)

        return max_neighbor

    def __write_neighbors (self, max_neighbor, file_to_write, weighted):
        file_to_write.write("%s %s%s"%(self.Graph.number_of_nodes(),max_neighbor, os.linesep))

        for nodes in self.Graph.nodes():
            file_to_write.write("%s "%label_sent(str(nodes)))
            nbrs = self.Graph.neighbors(nodes)
            nbr_count = 0
            for nbr in nbrs:
                if weighted:
                    file_to_write.write("%s %s "%(label_sent(str(nbr)),self.Graph[nodes][nbr]['weight']))
                else:
                    file_to_write.write("%s %s "%(label_sent(str(nbr)),"1.0"))
                nbr_count = nbr_count +1 

            if nbr_count < max_neighbor:
                for  x in range(nbr_count, max_neighbor):
                    file_to_write.write("%s %s " %("-1","0.0"))

            file_to_write.write("%s"%os.linesep)

        file_to_write.flush()
        file_to_write.close()

    def prepareSentsFile(self):
        sentfiletoWrite = open("%s.txt"%(self.sentsFile),"w")
        for result in self.postgresConnection.memoryEfficientSelect(["id","content"],\
             ["sentence"], [], [], ["id"]):
            for row_id in range(0,len(result)):
                id_ = result[row_id][0]
                content = gensim.utils.to_unicode(result[row_id][1].strip())
                content = self.utFunction.normalizeText(content, remove_stopwords=0)
                sentfiletoWrite.write("%s %s%s"%(label_sent(id_),' '.join(content), os.linesep))
            sentfiletoWrite.flush()
        sentfiletoWrite.close()

    def prepareData(self, pd):
        """
        It prepares neighbor data for regularized sen2vec. 
        The first line of the file will indicate how nodes 
        are in the file and max number of neighbors. If a 
        particular node has less number of neighbors than the 
        maximum numbers then "-1" should be written as 
        neighbor. For the unweighted version, all weights should 
        be 1.0. 
        """
        if pd <= 0: return 0 
        self.prepareSentsFile()

        self.Graph = nx.read_gpickle(self.graphFile)
        max_neighbor = self.__getMaxNeighbors()

        neighbor_file_w = open("%s_neighbor_w.txt"%(self.regsen2vReprFile), "w")
        neighbor_file_unw = open("%s_neighbor_unw.txt"%(self.regsen2vReprFile), "w")

        self.__write_neighbors (max_neighbor, neighbor_file_w, weighted=True)
        self.__write_neighbors (max_neighbor, neighbor_file_unw, weighted=False)
        self.Graph = nx.Graph()


    def __dumpVecs(self, reprFile, vecFile, vecRawFile):

        vModel = Word2Vec.load_word2vec_format(reprFile, binary=False)
        
        vec_dict = {}
        vec_dict_raw = {}

        for nodes in self.Graph.nodes():
            vec = vModel[label_sent(str(nodes))]
            vec_dict_raw[int(nodes)] = vec 
            vec_dict[int(nodes)] = vec /  ( np.linalg.norm(vec) +  1e-6)

        pickle.dump(vec_dict, vecFile)
        pickle.dump(vec_dict_raw, vecRawFile)

    def runTheBaseline(self, rbase, latent_space_size):
        if rbase <= 0: return 0 

        self.Graph = nx.read_gpickle(self.graphFile)

        wordDoc2Vec = WordDoc2Vec()
        wPDict = wordDoc2Vec.buildWordDoc2VecParamDict()
        wPDict["cbow"] = str(0) 
        wPDict["sentence-vectors"] = str(1)
        wPDict["min-count"] = str(0)
        wPDict["train"] = "%s.txt"%self.sentsFile
        wPDict["window"] = self.window_size
        
        wPDict["size"]= str(latent_space_size * 2)
        args = []

######################### Working for Weighted Neighbor File ################## 
        # neighborFile =  "%s_neighbor_w.txt"%(self.regsen2vReprFile)
        # wPDict["output"] = "%s_neighbor_w"%(self.regsen2vReprFile)
        # wPDict["neighborFile"], wPDict["beta"] = neighborFile, str(self.regBetaW)
        # args = wordDoc2Vec.buildArgListforW2VWithNeighbors(wPDict, 2)
        # self._runProcess (args)
        # self.__dumpVecs(wPDict["output"],\
        #      open("%s.p"%wPDict["output"], "wb"),\
        #      open("%s_raw.p"%wPDict["output"], "wb"))

        
######################### Working for UnWeighted Neighbor File ###################      
        neighborFile =  "%s_neighbor_unw.txt"%(self.regsen2vReprFile)
        wPDict["output"] = "%s_neighbor_unw"%(self.regsen2vReprFile)
        wPDict["neighborFile"], wPDict["beta"] = neighborFile, str(self.regBetaUNW)

        args = wordDoc2Vec.buildArgListforW2VWithNeighbors(wPDict, 2)
        self._runProcess (args)
        self.__dumpVecs(wPDict["output"],\
                open("%s.p"%wPDict["output"], "wb"),\
                open("%s_raw.p"%wPDict["output"], "wb"))
        self.Graph = nx.Graph()

    def generateSummary(self, gs, methodId, filePrefix,\
         lambda_val=1.0, diversity=False):
        if gs <= 0: return 0
        regsentvecFile = open("%s%s.p"%(self.regsen2vReprFile,\
             filePrefix),"rb")
        regsentvDict = pickle.load (regsentvecFile)
        
        summGen = SummaryGenerator (diverse_summ=diversity,\
             postgres_connection = self.postgresConnection,\
             lambda_val = lambda_val)

        summGen.populateSummary(methodId, regsentvDict)
        

    def __runEval(self, summaryMethodID, vecFileName, reprName):
        summaryMethodID = 2

        what_for =""
        vDict = {}
        
        try: 
            what_for = os.environ['VALID_FOR'].lower()
        except:
            what_for = os.environ['TEST_FOR'].lower()

        if  "rank" in what_for:
            vecFile = open("%s.p"%(vecFileName),"rb")
            vDict = pickle.load(vecFile)
        else:
            vecFile_raw = open("%s_raw.p"%(vecFileName),"rb")
            vDict = pickle.load(vecFile_raw)

        Logger.logr.info ("Regularized Dictionary has %i objects"%len(vDict))
        Logger.logr.info ("Performing evaluation for %s"%what_for)

        self.performEvaluation(summaryMethodID, reprName, vDict)

            
    def runEvaluationTask(self):
        summaryMethodID = 2 
        Logger.logr.info("Starting Regularized Sentence 2 Vector Evaluation")
        
        # regvecFile = "%s_neighbor_w"%(self.regsen2vReprFile)
        # reprName = "%s_neighbor_w"%self.latReprName
        # self.__runEval(summaryMethodID, regvecFile, reprName)

        regvecFile = "%s_neighbor_unw"%(self.regsen2vReprFile)
        reprName = "%s_neighbor_unw"%self.latReprName
        self.__runEval(summaryMethodID, regvecFile, reprName)

        
    def doHouseKeeping(self):
        """
        Here, we destroy the database connection.
        """
        self.postgresConnection.disconnectDatabase()