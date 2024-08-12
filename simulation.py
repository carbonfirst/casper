# Authors: Basundhara Chakrabarty, Shruti Jasoria

from CAP.CAP import CAP
from CAP.workload import Workload
import logging
from CAP.deploy import Deployer
import pickle
import pandas as pd
import numpy as np
import copy
import time
import os
import subprocess
from CAP.config import Config
from CAP.metrics import Metrics
import matplotlib.pyplot as plt


logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()])

LOGGER = logging.getLogger(__name__)

LOGGER.info("---------------------Starting CAP---------------------")

#These variables might need to be changed to simulate different scenarios within the same CAP object 
#Scheduler can take one of the following values - [carbon, latency, replay]
_scheduler="carbon"
_load_balancer_region="us-east-1"
# Number of hours to run the simulation for 
_hours=24

start_date="2022-08-17"
config_file="/nfs/obelix/users2/sjasoria/kasper/CAP/current_requests.pickle"
# Total duration of each hour's simulation
size_of_hour=30
# Number of times the request scheduler will be run in an hour
request_update_interval = 10
gobetween="192.168.245.71:3000"
exponential_workload=False
distribution_type='EXPONENTIAL'


#Global variables that will be used throughout the simulation
cap_obj=None
deploy_obj=None
workload_obj=None
metrics_obj=None
server_deployments=dict()
region_list=list()

#Global variables to store metrics
global_requests_to_df=None
global_requests_from_df=None
global_carbon_intensities=None
global_latencies=None

def start_gobetween():
    """
    Starts the load balancer gobetween
    Returns:
        process: Process object for the gobetween process
    """
    LOGGER.info("[INFO] Starting load balancer GoBetween")
    command = ['gobetween', '-c', 'gobetween/config/gobetween.toml']
    with open(os.devnull, 'w') as null_file:
        lb_process = subprocess.Popen(command,
                               stdout=null_file, stderr=null_file)
    return lb_process

def end_gobetween(lb_process):
    """
    Ends the load balancer gobetween
    Args:
        lb_process: Process object for the gobetween process
    """
    LOGGER.info("[INFO] Ending load balancer GoBetween")
    lb_process.kill()
    lb_process=None
    return


def create_kubernetes_setup():
    """
    Creates the kubernetes setup for the simulation
    """
    for region in region_list:
        server_deployments[region]=1.0
    deploy_obj.build_setup(server_deployments)
    return

def calculate_weights(requests):
    """
    Calculates the scheduler weights from the requests matrix and saves the same to a file
    Args:
        requests: i*j matrix where matrix[i][j] is the number of requests from region i that should be sent to region j
    Returns:
        weights: matrix of size n where matrix[i] is the proportion of requests region i should receive
    """
    LOGGER.info(f"Calculating regionwise weights from : {requests}")
    np_weights=np.sum(np.array(requests).astype(float),axis=0)
    # Compute the weighted average
    sum_weights=np.sum(np_weights)
    weights = ((np_weights * 100) / sum_weights).astype(int)
    serialized_weight_array = pickle.dumps(weights)
    with open(config_file, 'wb') as f:
        f.write(serialized_weight_array)
    return weights


def _initialize(hours=_hours,scheduler=_scheduler,load_balancer_region=_load_balancer_region):
    """
    Initializes the variables and objects to be used in the simulation
    Args:
        start_date: Start date of the simulation
        scheduler: Scheduler to be used for the simulation
        load_balancer_region: Region where the load balancer will be deployed
    """
    global cap_obj,metrics_obj,deploy_obj,region_list,workload_obj,global_requests_to_df,global_requests_from_df,global_carbon_intensities,global_latencies
    LOGGER.info(f"[INFO] Initializing the variables for the simulation")
    cap_obj = CAP(hours,start_date=start_date,load_balancer_region=load_balancer_region,exponential_workload=True)
    cap_obj.set_scheduler(scheduler)
    deploy_obj=Deployer()
    metrics_obj=Metrics()

    # Regions are ['ap-southeast-2', 'eu-central-1', 'eu-west-3', 'us-east-1', 'us-east-2','us-west-1':1]
    region_list=cap_obj.server_manager.region_names
    #LOGGER.info("[INFO] Regions:",region_list)
    workload_obj=Workload(region_list, duration=request_update_interval, traefik_srv="192.168.245.71")
    
    #create_setup()

    #Set metrics up with default values
    global_requests_to_df = pd.DataFrame(columns=region_list)
    global_requests_from_df=pd.DataFrame(columns=region_list)
    global_carbon_intensities=pd.DataFrame(columns=region_list)
    global_latencies=pd.DataFrame(columns=region_list)
    return

def _run():
    """
    Runs the simulation for the specified number of hours
    """
    # Start the load balancer traefik
    LOGGER.info(f"[INFO] Starting the load balancer Traefik for every region")
    global _hours,request_update_interval, cap_obj,deploy_obj,region_list,workload_obj,exponential_workload,global_requests_to_df,global_requests_from_df,global_carbon_intensities,global_latencies


    deploy_obj.start_traefik()
    prometheus_process=deploy_obj.start_prometheus()
    
    # Helper variable to store the carbon intensity of the current hour, to be stacked and used for plotting
    hourly_carbon_intensities=pd.DataFrame(columns=region_list)

    LOGGER.info(f"---------------------RUNNING FOR A TOTAL OF :{_hours} HOURS--------------------------------")
    LOGGER.info(f"---------------------RUNNING THE REQUEST SCHEDULER :{request_update_interval} times/hour---------------------")
    for hour in range(_hours):

        requests_from_total = {region:0 for region in region_list}
        requests_to_total = {region:0 for region in region_list}

        ###################### SERVER PROVISIONING ######################
        # Run CAP's provision function to get the number of servers to be deployed in each region
        LOGGER.info(f"---------------------Provisioning servers for hour:{hour}---------------------")

        servers_per_region,requests,carbon_intensities,latencies_matrix = cap_obj.provision(hour)

        LOGGER.info(f"[INFO] Servers / Region: {servers_per_region}")
        for servers,region in zip(servers_per_region,region_list):
                server_deployments[region]=servers

        # Patching the deployment with the number of servers / region
        LOGGER.info(f"[INFO] server_deployments: {server_deployments}")
        deploy_obj.patch_setup(server_deployments)
        ###################### SERVER PROVISIONING ######################
        
        # Calculate the weights from the requests matrix
        weights=calculate_weights(requests)

        # Calculate the weights by region, a convenient way to store the weights
        regionwise_weights = {region:weights[i] for i,region in enumerate(region_list)}
        print(type(regionwise_weights)) 
        LOGGER.info(f"[INFO] regionwise_weights: {regionwise_weights}")
         
        # Update the weights in the traefik deployment
        deploy_obj.update_traefik_weights(regionwise_weights)

        # total_requests_to= pd.DataFrame(index=region_list).astype(int)
        # total_requests_from= pd.DataFrame(index=region_list).astype(int)
        # total_request_service_time= pd.DataFrame(index=region_list).astype(float)

        total_requests_to= pd.Series(0, index=region_list)
        total_requests_from= pd.Series(0, index=region_list)   
        total_request_service_time= pd.DataFrame(0,columns=region_list, index=region_list).astype(float)

        ###################### REQUEST SCHEDULUNG ######################
        timesteps = int(size_of_hour/request_update_interval)
        # Calculate workload for scheduling requests
        if exponential_workload and _scheduler!='replay':
            cap_obj.generate_request_workload(requests, timestep, distribution_type)
        for timestep in range(timesteps):

            # build request batches to be sent during the hour by the scheduler
            print(f"---------------Running scheduler for timestep {timestep} for hour:{hour}---------------")
            if exponential_workload and _scheduler!='replay':
                batches = cap_obj.build_workload_batches(timestep)
            else:
                batches = cap_obj.build_batches(hour, request_update_interval=request_update_interval)

            # Reset the prometheus metrics stats before sending requests
            metrics_obj.reset_promestheus_stats()

            # Sends the batch of requests using the workload generator
            workload_obj.simulate_workload(batches)

            # Calculate the total requests received to each region and the total service time for each region
            requests_from, requests_to, request_service_time= metrics_obj.get_relevant_metrics()
            #total_requests_to = total_requests_to + requests_to
            total_requests_to = total_requests_to+ requests_to
            total_requests_from = total_requests_from + requests_from
            total_request_service_time = total_request_service_time + request_service_time

        ###################### REQUEST SCHEDULUNG ######################

        # Calculate the avg requests received to each region and the avg service time for each region

        avg_requests_to = total_requests_to/timesteps
        avg_requests_from = total_requests_from/timesteps
        avg_request_service_time = total_request_service_time/timesteps

        # Store the regionwise avg requests to that region in the current hour in a global df
        global_requests_to_df= global_requests_to_df.append(avg_requests_to,ignore_index=True)

        # Store the regionwise avg requests from that region in the current hour in a global df
        global_requests_from_df= global_requests_from_df.append(avg_requests_from,ignore_index=True)

        # Append the carbon intensity of the current hour to the helper variable
        hourly_carbon_intensities=hourly_carbon_intensities.append(pd.Series(carbon_intensities, index=hourly_carbon_intensities.columns),ignore_index=True)

        print("Before adding latency matrix:",avg_request_service_time)
        # Store the regionwise avg_request_service_time for a region for the current hour in a global df
        avg_request_service_time=avg_request_service_time+latencies_matrix
        print("After adding latency matrix:",avg_request_service_time)
        print("requests",requests)
        curr_latencies= avg_request_service_time.sum(axis=0)*np.sum(requests,axis=1)
        print("curr_latencies",curr_latencies)

        global_latencies=global_latencies.append(curr_latencies,ignore_index=True)
        #global_latencies=global_latencies.append(avg_request_service_time,ignore_index=True)

        print(global_requests_to_df)
        print(hourly_carbon_intensities)
        print(global_latencies)
    
    # End the load balancer traefik
    LOGGER.info(f"[INFO] Ending the load balancer Traefik for every region")
    deploy_obj.stop_traefik()
    deploy_obj.stop_prometheus(prometheus_process)

    # Calculate the carbon intensity incurred by the requests executed in each region
    global_carbon_intensities=hourly_carbon_intensities*global_requests_to_df
    print(global_carbon_intensities)

    return

def _print_and_save_metrics():
    """
    Prints the metrics collected during the simulation and saves them as csv 
    """
    LOGGER.info(f"---------------------GLOBAL REQUESTS FROM DATAFRAME---------------------")
    LOGGER.info(global_requests_from_df)
    global_requests_from_df.to_csv(f'/nfs/obelix/users2/sjasoria/kasper/dataframes/{_scheduler}/global_requests_from_df.csv',index=False)
    LOGGER.info(f"---------------------GLOBAL REQUESTS TO DATAFRAME---------------------")
    LOGGER.info(global_requests_to_df)
    global_requests_to_df.to_csv(f'/nfs/obelix/users2/sjasoria/kasper/dataframes/{_scheduler}/global_requests_to_df.csv',index=False)
    LOGGER.info(f"---------------------GLOBAL CARBON INTENSITIES---------------------")
    LOGGER.info(global_carbon_intensities)
    global_carbon_intensities.to_csv(f'/nfs/obelix/users2/sjasoria/kasper/dataframes/{_scheduler}/global_carbon_intensities.csv',index=False)
    LOGGER.info(f"---------------------GLOBAL LATENCIES---------------------")
    LOGGER.info(global_latencies)
    global_latencies.to_csv(f'/nfs/obelix/users2/sjasoria/kasper/dataframes/{_scheduler}/global_latencies.csv',index=False)
    return

def _plot():
    """
    Plots the data collected during the simulation
    """
    colors = ['blue', 'red', 'green', 'cyan', 'magenta', 'yellow']
    for i, col in enumerate(global_carbon_intensities.columns):
        plt.plot(global_carbon_intensities.index, global_carbon_intensities[col], color=colors[i], label=col)
    plt.legend()
    plt.show()
    return

def main():
    
    _initialize()
    _run()
    _print_and_save_metrics()
    #_print_metrics()
    # w={'ap-southeast-2': 0, 'eu-central-1': 0, 'eu-west-3': 1, 'us-east-1': 1, 'us-east-2': 1, 'us-west-1': 1}
    # print(w)
    # deploy_obj.update_traefik_weights(w)
    # create_kubernetes_setup()
    #deploy_obj.teardown_setup()
    #traefik_processes=start_traefik()
    #end_traefik(traefik_processes)
    

if __name__ == '__main__':
    main()
