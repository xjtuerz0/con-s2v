#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os 
import sys 
import math 
import pickle
from abc import ABCMeta, abstractmethod
from log_manager.log_config import Logger
from baselineEvaluator.BaselineEvaluator import BaselineEvaluator
from baselineRunner.SequentialRegularizedSen2VecRunner import SequentialRegularizedSen2VecRunner



class SeqRegSentEvaluator(BaselineEvaluator):
	def __init__(self, *args, **kwargs):
		"""
		Sequential Regularized Sentence 2 Vector 
		Evaluator
		"""
		BaselineEvaluator.__init__(self, *args, **kwargs)
		self.system_id_list = []

	def getOptimumParameters(self, f, optPDict, latent_space_size):
		self._setmetricString ()
		filePrefix = "_neighbor_unw"
		unw_opt_seq_reg = None 

		seqregs2v = SequentialRegularizedSen2VecRunner(self.dbstring)
		for beta in self.beta_list:
			Logger.logr.info("[SeqRegS2V] Starting Running "+\
				" Baseline for Beta = %s" %beta)
			seqregs2v.seqregunw_beta = beta
			seqregs2v.window_size = optPDict["window"]
			if beta== self.beta_list[0]:
			   seqregs2v.prepareData(1)

			self.metric[beta] = self.evaluate(seqregs2v, filePrefix, latent_space_size)	
			Logger.logr.info("[SeqRegS2V] UNW_%s for %s = %s" %(self.metric_str, beta, self.metric[beta]))
			
		unw_opt_seq_reg = max(self.metric, key=self.metric.get)
		Logger.logr.info("[SeqRegS2V] BetaUNW=%s" %(unw_opt_seq_reg))	
		optPDict['unw_opt_seq_reg'] = unw_opt_seq_reg
		f.write("[SeqRegS2V] BetaUNW : %.2f%s" %(unw_opt_seq_reg, os.linesep))
		f.write("[SeqRegS2V] BetaUNW %ss: %s%s" %(self.metric_str, self.metric, os.linesep))
		f.flush()
		return optPDict

	def evaluateOptimum(self, pd, rbase, latent_space_size, optPDict, f):
		
		filePrefix = "_neighbor_unw"
		f.write("[SeqRegS2V] Optimal beta is: %s%s" %(optPDict["unw_opt_seq_reg"], os.linesep))	
		seqregs2v = SequentialRegularizedSen2VecRunner(self.dbstring)
		seqregs2v.seqregunw_beta = optPDict['unw_opt_seq_reg']
		seqregs2v.window_size = optPDict["window"]
		self.system_id_list.append(seqregs2v.system_id)
		self.writeResults(pd, rbase, latent_space_size, seqregs2v, filePrefix, f)