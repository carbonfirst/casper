# Authors: Basundhara Chakrabarty, Shruti Jasoria

import numpy as np
import pandas as pd
from scipy.stats import expon
from .config import Config
from .milp_scheduler import MilpScheduler
from .request import RequestBatch
from .server import ServerManager
from .util import Util


class CAP:
    
	def __init__(self, hours, load_balancer_region="ap-southeast-2",start_date="2022-08-13",exponential_workload=False) -> None:
		Config.TIMESTEPS=hours
		Config.START_DATE = start_date
		Config.LOAD_BALANCER_REGION=load_balancer_region
		Config.EXPONENTIAL_WORKLOAD=exponential_workload
		self.server_manager = ServerManager()
		# if Config.EXPONENTIAL_WORKLOAD and Config.SCHEDULER!="replay":
			# self.generate_exponential_batches(self.server_manager)
		self.request_workload = None			

	def provision(self, hour):
		
		batches = self.build_batches(hour)
		servers_per_region=None
		requests=None
		carbon_intensities=None
		latencies=None
		if Config.SCHEDULER == "replay":
			print("Provisioning for replay")
			servers_per_region, requests = self.servers_per_region_predetermined(hour)
			carbon_intensities = [region.carbon_intensity[hour] for region in self.server_manager.regions]
			latencies = np.array(
				[[region.latency(batch.region) for region in self.server_manager.regions] for batch in batches]
			)

		else:
			print("Provisioning for ", Config.SCHEDULER)
			servers_per_region,requests,carbon_intensities,latencies = MilpScheduler.schedule_servers( 
				batches, 
				self.server_manager, 
				hour
			)
		# move servers to regions according to scheduling estimation the next hour
		print("servers_per_region",servers_per_region)
		print("Requests Redirected:",requests)
		return servers_per_region,requests,carbon_intensities,latencies
		

	def build_batches(self, hour, request_update_interval=None):
		"""Adds creates batch of work to inject called by main()

		Args:
			conf: Runtime configurations to retrieve work building frequency
			server_manager: Central server manager object that i.e. holds regions
			t: current timestep
			request_update_interval: Frequency at which tasks are built. Defaults to None.
			
		Returns:
			Batch of requests
		"""
		request_batches = []
		#print("Regions:",server_manager.regions)
		for region in self.server_manager.regions:
			# Gets per hour
			this_hour_requests = region.get_requests_per_interval(hour)
			#print("Region: ", region, "Rate (obtained from data file, not from conf): ", this_hour_requests)
			if Config.REQUEST_RATE:
				this_hour_requests = Config.REQUEST_RATE
			# if request_update_interval:
			# 	this_hour_requests //= request_update_interval
			new_batch = RequestBatch(region.name, this_hour_requests, region)
			request_batches.append(new_batch)
		print("Built Request Batches for hour:{0}".format(hour))
		print(request_batches)
		return request_batches

	def build_exponential_batches(self, hour, request_update_interval=None):
		"""
		This method uses exponential workload to build batches
		"""
		request_batches=[]
		#print("Regions:",server_manager.regions)
		for region in self.server_manager.regions:
			# Gets per hour
			this_hour_requests = region.get_expo_requests_per_interval(hour)
			if Config.REQUEST_RATE:
				this_hour_requests = Config.REQUEST_RATE
			if request_update_interval:
				this_hour_requests //= request_update_interval
			new_batch = RequestBatch(region.name, this_hour_requests, region)
			request_batches.append(new_batch)
		print("Built Request Batches for hour:{0}".format(hour))
		print(request_batches)
		return request_batches

	def generate_exponential_batches(self):
		"""
		This method generates workload for each region. The workload follows 
		exponential distribution and sum of the requests is equal to sum of requests
		used for provisioning
		"""
		print("Generating exponential workload...")
		expo_df = pd.DataFrame()
		timesteps = Config.TIMESTEPS
		for region in self.server_manager.regions:
			total_requests_region = 0
			for hour in range(timesteps + 1):
				total_requests_region += region.get_requests_per_interval(hour)
			expon_distribution = expon.rvs(size=(timesteps+1))
			expon_distribution = expon_distribution*total_requests_region/np.sum(expon_distribution)
			expon_distribution = np.round(expon_distribution)
			expo_df[region.name] = expon_distribution
		
		for region in self.server_manager.regions:
			region.exponential_df = expo_df
		print(region.exponential_df)
		return

	def servers_per_region_predetermined(self, hour):
		rates = np.zeros(len(self.server_manager.regions), dtype=np.float64)
		for region in self.server_manager.regions:
			# print(region.get_requests_per_interval_per_region(t))
			rates += region.get_requests_per_interval_per_region(hour)
			# TODO - This loop is adding all the same latencies multiple times
			# The data is already at an hourly
			break 
		print("rates: ", rates)
		servers_per_region = np.ceil(rates / Config.SERVER_CAPACITY).astype(np.int64)
		print("servers_per_region_predetermined: ",servers_per_region)
		return servers_per_region, np.diag(rates)

	def requests_predetermined(conf, request_batches, server_manager, t, request_update_interval):
		print("requests_predetermined running...")
		n = len(server_manager.regions)
		requests_per_region = np.zeros([n, n], dtype=np.float64) ## Why is it nxn here??
		print(requests_per_region)
		for i, region in enumerate(server_manager.regions):
			requests_per_region[i][i] = (region.get_requests_per_interval_per_region(t) / request_update_interval)[i]
		print("Requests per region") 
		print(requests_per_region)
		return latency, carbon_intensity, requests_per_region		

	def set_scheduler(self, scheduler):
		Config.SCHEDULER = scheduler

	def generate_request_workload(self, requests, timesteps, distribution_type):
		requests_from_region = [sum(l) for l in requests]
		region_names = Util.region_names()
		distribution = None
		self.request_workload = pd.DataFrame()
		for request, region_name in zip(requests_from_region, region_names):
			print("Request: ", request)
			print("region_name: ", region_name)
			distribution = None
			if distribution_type == 'EXPONENTIAL':
				# f(x) = e^(-x)
				# expon.pdf(x, loc, scale) is identically equivalent to 
				# expon.pdf(y) / scale with y = (x - loc) / scale. 
				# Scale is chosen such that the values don't go to far from 1
				# Otherwise it'll create situation where the pods can't handle the 
				# traffic
				distribution = expon.rvs(size=(timesteps), scale=0.5)
			elif distribution_type == 'BIMODAL':
				d1 = np.random.normal(loc=1,scale=0.12,size=int(np.floor(timesteps/2)))
				d2 = np.random.normal(loc=1.1,scale=0.06,size=int(np.ceil(timesteps/2)))
				distribution = np.concatenate([d1,d2])
			elif distribution_type == 'TRIMODAL':
				d1 = np.random.normal(loc=0.9,scale=0.07,size=int(np.floor(timesteps/3)))
				d2 = np.random.normal(loc=1,scale=0.07,size=int((timesteps-2*np.floor(timesteps/3))))
				d3 = np.random.normal(loc=1.1,scale=0.07,size=int(np.floor(timesteps/3)))
				distribution = np.concatenate([d1,d2,d3])
			else:
				raise Exception("distribution_type can take one of the values - EXPONENTIAL, BIMODAL, TRIMODAL")

			print("Distribution: ", distribution)
			distribution = np.ceil(distribution).astype(int)
			distribution = [x * request for x in distribution]
			self.request_workload[region_name] = distribution
			print(f"After exponential: Region: {region_name}, Distribution: {distribution}")


	def build_workload_batches(self, timestep):
		request_batches=[]
		requests = self.request_workload.iloc[timestep]
		for region in self.server_manager.regions:
			new_batch = RequestBatch(region.name, requests[region.name], region)
			request_batches.append(new_batch)
		return request_batches
