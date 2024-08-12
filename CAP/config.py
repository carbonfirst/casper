# Authors: Basundhara Chakrabarty, Shruti Jasoria
# This file has all the constants used for the experiment. Make changes here before
# running any simulations

class Config:
	# The total number of hours
	TIMESTEPS=1
	# The number of minutes between each scheduling
	# REQUEST_UPDATE_INTERVAL=10
	# Specify a constant request rate per hour
	REQUEST_RATE=0
	# Save file to /saved with the following format YYYY-MM-DD_hh:mm:ss
	SAVE=True
	# Start date in ISO format (YYYY-MM-DD)
	START_DATE="2022-08-13"
	# Maximum latency allowed
	MAX_LATENCY=500
	# Maximum pool of servers
	MAX_SERVERS=500
	# Maximum servers that can be spawned in a region
	MAX_SERVERS_PER_REGION=100
	# The capacity of each server
	SERVER_CAPACITY=10 #TODO
	# Load Balancer Region
	LOAD_BALANCER_REGION="ap-southeast-2"
	# The dataset we want to load our data from - [wiki, akamai]
	DATASET="wiki"
	# The file name from where we want to load carbon intensities data
	CARBON_INTENSITY_FILENAME="carbon_intensities.csv"
	# The file name from where we want to load requests data
	REQUEST_DATA_FILENAME="requests.csv"
	# The file name from where we want to load inter-region latency data
	LATENCY_FILENAME ="latency.csv"
	# The file name from where we want to load time offset data for the regions
	TIME_OFFSET_FILENAME="offset.csv"
	# Define the scheduler you wish to use: carbon/latency/replay
	# replay has no optimizations
	SCHEDULER="carbon"
	# Generate exponential workload
	EXPONENTIAL_WORKLOAD=False
	# Print information from every timestep
	VERBOSE=True
	# Print output of MILP scheduler
	VERBOSE_MILP=True
