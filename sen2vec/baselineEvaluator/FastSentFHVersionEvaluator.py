#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os 
import sys 
import math 
import pickle
from abc import ABCMeta, abstractmethod
from log_manager.log_config import Logger
from baselineRunner.FastSentFHVersionRunner import FastSentFHVersionRunner
from baselineEvaluator.BaselineEvaluator import BaselineEvaluator


class FastSentFHVersionEvalutor(BaselineEvaluator):
	def __init__(self, *args, **kwargs):
		"""
		"""
		BaselineEvaluator.__init__(self, *args, **kwargs)
		self.system_id_list = []

	def getOptimumParameters(self, f, optPDict, latent_space_size):
		self._setmetricString ()
		window_opt_fh = None 
		latent_space_size = latent_space_size * 2
		fhBaseline =  FastSentFHVersionRunner(self.dbstring, autoencode=True)
		for window in self.window_size_list:
			Logger.logr.info("[FASTSENT (+AE)] Starting Running "+\
					" Baseline for Window = %s" %window)				
			fhBaseline.window_size  = window
			if 	window == self.window_size_list[0]: 
				fhBaseline.prepareData(1)		
			self.metric[window] = self.evaluate(fhBaseline, "",latent_space_size)
			Logger.logr.info("[FASTSENT (+AE)] %s for window %s = %s"\
				 %(self.metric_str, window, self.metric[window]))
		window_opt_fh = max(self.metric, key=self.metric.get) 
		f.write("[FASTSENT (+AE)] Optimal window size for %s in fhbaseline is %s%s"\
				%(self.metric_str, window_opt_fh, os.linesep))
		f.write("[FASTSENT (+AE)] %ss: %s%s" %(self.metric_str, self.metric, os.linesep))
		f.flush()

		optPDict["fh-ae-window"] = window_opt_fh
		return optPDict

	def evaluateOptimum(self, pd, rbase, latent_space_size, optPDict, f):
		f.write("[FASTSENT (+AE)] Optimal Window for fh (+AE) is: %s%s" %(optPDict["fh-ae-window"], os.linesep))	
		latent_space_size = latent_space_size * 2
		fhBaseline =  FastSentFHVersionRunner(self.dbstring, autoencode=True)
		fhBaseline.window = optPDict["fh-ae-window"]
		self.system_id_list.append(fhBaseline.system_id)
		self.writeResults(pd, rbase, latent_space_size, fhBaseline, "", f)




		