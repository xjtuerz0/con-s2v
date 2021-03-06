#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os 
import sys 
from log_manager.log_config import Logger 
import networkx as nx 
from copy import deepcopy
import numpy as np 

class WeightedIterativeUpdateRetrofitter:
    def __init__(self, *args, **kwargs):
      self.numIters = kwargs['numIter']
      self.nx_Graph = kwargs['nx_Graph']

    def retrofitWithIterUpdate(self, sen2vec, alpha=-1.0):
      """
      If alpha is initialized to negative, then we assume 
      the value is not initialized and initialized it 
      with the summation of weight. In all other case, 
      we use user configuration.

      Here Beta_ij = 1.0 / d_i
      """
      newSen2Vecs = deepcopy(sen2vec)
      normalized_newSen2Vecs = deepcopy(sen2vec)

      allSentenceIds = list(newSen2Vecs.keys())

      for iter_ in range(self.numIters):
        for sentenceId in allSentenceIds:
          sentNeighbors = self.nx_Graph.neighbors(sentenceId)
          numNeighbors = len(sentNeighbors)
          if numNeighbors == 0:
            continue
          
          #total_weight = 0.0
          if alpha <= 0.0:
             alpha = 1.0

          newVec = alpha * numNeighbors * sen2vec[sentenceId]
          for neighborSentId in sentNeighbors:
            newVec += self.nx_Graph[sentenceId][neighborSentId]['weight'] * newSen2Vecs[neighborSentId]
            #total_weight = total_weight + self.nx_Graph[sentenceId][neighborSentId]['weight']

          #newVec += alpha * sen2vec[sentenceId]
          newSen2Vecs[sentenceId] = newVec/(alpha*numNeighbors + numNeighbors)

      for Id  in allSentenceIds:
        vec = newSen2Vecs[Id] 
        normalized_newSen2Vecs[Id] = vec / ( np.linalg.norm(vec) +  1e-6)

      # Logger.logr.info("Norm of the vector = %f"%np.linalg.norm(newSen2Vecs[allSentenceIds[0]]))

      return newSen2Vecs, normalized_newSen2Vecs
