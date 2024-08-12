# Authors: Basundhara Chakrabarty, Shruti Jasoria

import os
import logging
import subprocess
import time
from .request import RequestBatch
import requests
import pickle

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()])

LOGGER = logging.getLogger(__name__)

class Workload:
    """Imitates a batch of requests
    """
    def __init__(self, region_list, duration=10, traefik_srv="192.168.245.71"):
        """
        Args:
            regions= Regions assigned to complete the requests
            duration: Duration of the workload
            server: Backend server to which the requests are sent
        """
        self.regions= region_list
        self.num_sessions = len(self.regions)
        self.duration  = duration
        LOGGER.info(f'Duration of the workload is {self.duration} seconds')
        self.traefik_srv="192.168.245.71"
        self.traefik_ports= {'ap-southeast-2':3001, 'eu-central-1':3002, 'eu-west-3':3003, 'us-east-1':3004, 'us-east-2':3005,'us-west-1':3006}
        self.config_file="/nfs/obelix/users2/sjasoria/kasper/CAP/current_requests.pickle"
        self.lb_stats_backend="http://192.168.245.71:3001/servers/sample/stats"
        self.region_info= { 'eu-central-1':{'backend_ip':'192.168.245.71','backend_port':31997},
                        'eu-west-3':{'backend_ip':'192.168.245.71','backend_port':30543},
                        'us-east-1':{'backend_ip':'192.168.245.74','backend_port':31159},
                        'us-east-2':{'backend_ip':'192.168.245.74','backend_port':32535},
                        'us-west-1':{'backend_ip':'192.168.245.75','backend_port':31930},
                        'ap-southeast-2':{'backend_ip':'192.168.245.75','backend_port':30738}}

        self.processes={region:None for region in self.regions}
        self.throughput_per_region = {region:0 for region in self.regions}
        self.exp_requests_to={region:0 for region in self.regions}
        self.requests_from={region:0 for region in self.regions}
        self.requests_to={region:0 for region in self.regions}

        self.prev_request_stats={'total_connections':{region:0 for region in self.regions},'refused_connections':{region:0 for region in self.regions}}
        return
        

    def load_batch(self,batches=None):
        """
        Loads the batch of requests to the server
        Args:
            batches: List of batches of requests
        """
        LOGGER.info(f"[INFO] Loading batch of requests")
        for batch in batches:
            self.throughput_per_region[batch.name] = batch.load
        return

    def start_session(self, region) -> subprocess.Popen:
        """
        Starts the httpmon workload session for a region
        Args:
            region: Region for which workload session is started
        Returns:
            process: Process object for the httpmon process
        """
        command = [
                        "/nfs/obelix/users2/sjasoria/httpmon/httpmon",
                        "--url",
                        f"http://{self.traefik_srv}:{self.traefik_ports[region]}",
                        "--thinktime",
                        "1",
                        "--concurrency",
                        # str(self.throughput_per_region[region]),
                        "100",
                        "--count",
                        str(self.throughput_per_region[region]*self.duration),
                        "--terminate-after-count",
                    ]
        LOGGER.info(f"[INFO] Starting session for region {region} with throughput {self.throughput_per_region[region]}  command={' '.join(command)}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return process

    def end_session(self,region):
        """
        Ends the httpmon workload session for a region
        Args:
            region: Region for which workload session is to be ended
        """
        LOGGER.info(f"[INFO] Ending session for region {region}")
        self.processes[region].wait()
        self.processes[region]=None
        return

    def verify_requests_to(self):
        """
        Calculates the expected number of requests sent to each region based on weights, and the actual number of requests sent to each region
        
        """
        LOGGER.info(f"[INFO] Verifying requests to each region!")
        with open(self.config_file, 'rb') as f:
            serialized_weights = f.read()
        weights = pickle.loads(serialized_weights)
        # Order of regions: ([Region(ap-southeast-2), Region(eu-central-1), Region(eu-west-3), Region(us-east-1), Region(us-east-2), Region(us-west-1)])
        regionwise_weights = {region:weights[i] for i,region in enumerate(self.regions)}
        LOGGER.info(f"[INFO] Calculating expected requests to each region with weights {regionwise_weights}")

        total_requests=sum(self.requests_from.values())
        sum_weights=sum(regionwise_weights.values())
        for region in self.regions:
            self.exp_requests_to[region]=int(regionwise_weights[region]*total_requests/sum_weights)
            LOGGER.info(f"[INFO] Expected requests to {region}: {self.exp_requests_to[region]}, Actual requests to {region}: {self.requests_to[region]}")
        return

    def calculate_server_stats(self):
        response = requests.get(self.lb_stats_backend)
        backend_stats=dict()
        backend_json = response.json()

        for backend in backend_json['backends']:
            print(backend)
            host,port=backend['host'],backend['port']
            region = [k for k, v in self.region_info.items() if v['backend_ip'] == host and str(v['backend_port']) == port][0]
            
            self.requests_to[region]=backend['stats']['total_connections']
            self.prev_request_stats['total_connections'][region]=backend['stats']['total_connections']
            self.prev_request_stats['refused_connections'][region]=backend['stats']['refused_connections']
        
        print("self.requests_from",self.requests_from)
        print("self.requests_to",self.requests_to)
        total_requests_from=sum(self.requests_from.values())
        total_requests_to=sum(self.requests_to.values())
        LOGGER.info(f"[INFO] Total requests from all regions: {total_requests_from}")
        LOGGER.info(f"[INFO] Total requests to all regions: {total_requests_to}")

        return



    def reset_request_counts(self):
        """
        Resets the request counts for each region
        """
        LOGGER.info(f"[INFO] Resetting request counts")
        self.processes={region:None for region in self.regions}
        self.exp_requests_to={region:0 for region in self.regions}
        self.requests_from={region:0 for region in self.regions}
        self.requests_to={region:0 for region in self.regions}

        return

    def simulate_workload(self, batches):
        """
        Simulates the workload for a duration with the given throughput
        Args:
            batches: List of batches of requests
        """

        self.load_batch(batches)

        LOGGER.info(f"[INFO] Simulating workload with throughputs {self.throughput_per_region} for {self.duration} seconds")
        for region in self.regions: 
            self.processes[region] = self.start_session(region)

        for region in self.regions:
            self.end_session(region)

        time.sleep(5)

        return

    def __repr__(self) -> str:
        return f"Workload({self.num_sessions}, load={self.duration}, server={self.server} ,throughput={self.throughput_per_region})"

if __name__ == "__main__":
    regions = ['ap-southeast-2', 'eu-central-1', 'eu-west-3', 'us-east-1', 'us-east-2','us-west-1']
    duration = 10
    
    throughput = {region: 100 for region in regions}
    # workload.simulate_workload(throughput)
    # print(workload)
    # print(workload.requests_from)
    # print(workload.requests_to)

    workload = Workload(regions, duration)
    process=workload.start_load_balancer()