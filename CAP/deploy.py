from kubernetes import client, config, watch
import os
from .deploy_utils import *
import logging
import copy
import subprocess
import re
import yaml
from collections import OrderedDict
import time

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()])

LOGGER = logging.getLogger(__name__)

class Deployer:
    def __init__(self, start_date="2022-08-13") -> None:
        config.load_kube_config()
        #Create objects for all API endpoints required
        self.apps_api = client.AppsV1Api()
        self.core_api=v1 = client.CoreV1Api()
        self.n_replicas=1

        self.node_region_mapping={'obelix71.cs.umass.edu':['eu-central-1','eu-west-3'],'obelix74.cs.umass.edu':['us-east-1','us-east-2'],'obelix75.cs.umass.edu':['us-west-1','ap-southeast-2']}

        # The contents of self.locations can be automatically populated from the output of kubectl get svc after startup in the build_setup() function
        # Regions are ['ap-southeast-2', 'eu-central-1', 'eu-west-3', 'us-east-1', 'us-east-2','us-west-1':1]
        self.locations=OrderedDict()
        self.locations['ap-southeast-2']= None
        self.locations['eu-central-1']= None
        self.locations['eu-west-3']= None
        self.locations['us-east-1']= None
        self.locations['us-east-2']= None
        self.locations['us-west-1']= None
        self.get_location_info()

        if any(value is None for value in self.locations.values()):
            LOGGER.info("[INFO] : Locations not populated or incorrectly populated. Please run build_setup() to populate locations!")
        else:
            LOGGER.info("[INFO] : Locations populated correctly!")

        # self.locations['ap-southeast-2']= {'replicas': 1, 'svc-port': 31145, 'load_balancer_ip': '192.168.245.75'}
        # self.locations['eu-central-1']= {'replicas': 1, 'svc-port': 31444, 'load_balancer_ip': '192.168.245.71'}
        # self.locations['eu-west-3']= {'replicas': 1, 'svc-port': 31477, 'load_balancer_ip': '192.168.245.71'}
        # self.locations['us-east-1']= {'replicas': 1, 'svc-port': 30043, 'load_balancer_ip': '192.168.245.74'}
        # self.locations['us-east-2']= {'replicas': 1, 'svc-port': 30896, 'load_balancer_ip': '192.168.245.74'}
        # self.locations['us-west-1']= {'replicas': 1, 'svc-port': 30876, 'load_balancer_ip': '192.168.245.75'}
        
        self.app='kiwix-serve'
        self.secret_name="regcred"
        self.cpu_per_server=0.01
        self.cpu_epsilon=0.001
        self.container_resources={'cpu':{'requested':"0.01","limit":"0.1"},'memory':{'requested':"100M","limit":"400M"}}
        self.region_list=list(self.locations.keys())
        self.services=dict()
        self.deployments=dict()
        self.server_regions_map={region:1 for region in self.region_list}
        self.traefik_config_file="/nfs/obelix/users2/sjasoria/kasper/traefik/traefik_dynamic.yaml"
        self.traefik_processes=dict()
        return

    #Labels each node with the app name, and by each location provided
    def label_nodes(self):
        node_list = self.core_api.list_node()
        for node in node_list.items:      
            node.metadata.labels['app']=self.app
            curr_locations=self.node_region_mapping[node.metadata.name]
            LOGGER.info(f"------------------- Labelling nodes: {node.metadata.name}, {curr_locations} ------------------")
            for location in curr_locations:
                node.metadata.labels[location]='True'
            body={ "metadata":node.metadata}
            try:
                self.core_api.patch_node(node.metadata.name, body)
            except Exception as e:
                LOGGER.info(f"[FAILURE]: Failed to label node {node.metadata.name} CAUSE: {e}")
                print("Failed to label nodes!")
        LOGGER.info(f"[INFO]: Labelled all nodes!")
        return

    def start_traefik(self):
        """
        Starts the load balancer traefik
        Returns:
            traefik_processes : dict{name:process}: Dictionary of process objects for the traefik processes mapped to the region names
        """
        LOGGER.info("[INFO] Starting load balancer Traefik for each region")
        for region in self.region_list:
            traefik_static_config_file=f"traefik/traefik-{region}.yaml"
            command = ['./traefik/traefik', '--configFile', traefik_static_config_file]
            with open(os.devnull, 'w') as null_file:
                self.traefik_processes[region] = subprocess.Popen(command,
                                    stdout=null_file, stderr=null_file)
        return

    def update_traefik_backends(self):
        """
        Updates the traefik config file with the new backend information
        """
        # Load the YAML file
        with open(self.traefik_config_file, 'r') as f:
            traefik_config = yaml.safe_load(f)
        LOGGER.info(f"[INFO] Updating traefik config file with new backends IP and ports")
        for service in traefik_config['http']['services']:
            if service == 'app':
                continue 
            traefik_config['http']['services'][service]['loadBalancer']['servers'][0]['url'] = f"http://{self.locations[service]['load_balancer_ip']}:{self.locations[service]['svc-port']}"
            print("Changed the backend: ", service, traefik_config['http']['services'][service]['loadBalancer']['servers'][0]['url'])
        # Write the updated dictionary back to the YAML file
        with open(self.traefik_config_file, 'w') as f:
            yaml.dump(traefik_config, f)
        return

    def update_traefik_weights(self,weights):
        """
        Updates the traefik config file with the new weights obtained from CAP output
        Args:
            weights: Dictionary of load balancing weights mapped to each region
        """
        # Load the YAML file
        with open(self.traefik_config_file, 'r') as f:
            traefik_config = yaml.load(f, Loader=yaml.FullLoader)
        time.sleep(0.5)
        LOGGER.info(f"[INFO] Updating traefik config file with new weights: {weights}")
        for service in traefik_config['http']['services']['app']['weighted']['services']:
            print(weights[service['name']])
            service['weight'] = str(weights[service['name']])
            print("Changed the weight: ", service)
        with open(self.traefik_config_file, 'w') as f:
            yaml.dump(traefik_config, f)
        time.sleep(0.5)
        return
           

    def stop_traefik(self):
        """
        Terminates the traefik process for all regions
        Args:
            traefik_processes: Dictionary of process objects for the traefik processes mapped to the region names
        """
        LOGGER.info("[INFO] Ending load balancer Traefik for each region")
        for region in self.region_list:
            self.traefik_processes[region].kill()
            self.traefik_processes[region]=None
        return
    
    def start_prometheus(self):
        """
        Starts the Metric aggregator prometheus
        Returns:
            prometheus_process : The prometheus process object
        """
        LOGGER.info("[INFO] Starting the Metric aggregator prometheus")
        command = ['./prometheus/prometheus-2.44.0-rc.1.linux-amd64/prometheus', '--config.file=prometheus/prometheus-2.44.0-rc.1.linux-amd64/prometheus.yml', "--web.enable-admin-api"]
        with open(os.devnull, 'w') as null_file:
            prometheus_process = subprocess.Popen(command,
                                    stdout=null_file, stderr=null_file)
        return prometheus_process

    def stop_prometheus(self,prometheus_process):
        """
        Terminates the Metric aggregator prometheus
        Args:
            prometheus_process : The prometheus process object
        """
        LOGGER.info("[INFO] Ending Prometheus")
        prometheus_process.kill()
        return

    def get_location_info(self):
        """
        Gets the location information(region: Service IP and port) from the kubernetes cluster using kubectl get svc
        To be run after building the cluster using the build_setup() function
        """
        cmd = "kubectl get svc"
        output = subprocess.check_output(cmd, shell=True).decode("utf-8")

        # Parse the output into a dictionary
        pattern = r'^(kiwix-serve-\S+)\s+LoadBalancer\s+\S+\s+(\d+\.\d+\.\d+\.\d+)\s+\d+:(\d+)/\S+.*$'
        matches = re.findall(pattern, output, re.MULTILINE)
        for match in matches:
            region_name = re.search(r'kiwix-serve-(\w+-\w+-\d+)', match[0]).group(1)
            load_balancer_ip = match[1]
            svc_port = match[2]
            self.locations[region_name] = {'replicas': 1, 'svc-port': int(svc_port), 'load_balancer_ip': load_balancer_ip}
        return

    def calculate_resources(self,n_servers):
        max_cpu_allotment=self.cpu_per_server*n_servers+self.cpu_epsilon
        curr_container_resources=copy.deepcopy(self.container_resources)
        curr_container_resources['cpu']['requested']=str(0.9 * max_cpu_allotment)
        curr_container_resources['cpu']['limit']=str(max_cpu_allotment)
        return curr_container_resources
    
    def build_setup(self,server_deployments):
        
        container_spec={'name':'kiwix-serve',
                        'image':'casperumass/casper:casper-kiwix',
                        'n_containers':1,
                        'labels':{'app':self.app,'location':'us-west'},
                        'node_selector':None,
                        'container_port':8080,
                        }
        deploy_spec={   'name':None,
                        'pod-template':None,
                        'match_labels':{"app": "kiwix-serve"},
                        'n_replicas': self.n_replicas
                        }
        service_spec= {'type':'LoadBalancer',
                        'load_balancer_ip':None,
                        'selector':{"app": "kiwix-serve","location":None},
                        'name':'kiwix-serve-load-balancer',
                        'port':8080}

        registry = {
                    "username": "USERNAME",
                    "password": "TOKEN",
                    "email": "YOUR@EMAIL.COM",
                    "registry": "https://index.docker.io/v1/"
                    }

        LOGGER.info(f"------------------- Setup Started------------------")
        #Create the secret to pull the image from DockerHub
        try:
            create_kube_secret(client,self.core_api,registry,self.secret_name)
        except:
            pass

        LOGGER.info(f"------------------- Locations: {self.region_list} -------------------")
        for location in self.region_list:
            container_spec['node_selector']={location:'True'}
            container_spec['labels']['location']=location
            deploy_spec['n_replicas']=self.locations[location]['replicas']
            deploy_spec['name']=self.app+"-"+location
            curr_container_resources=self.calculate_resources(server_deployments[location])
            deploy_spec['pod_template']=create_pod_template(client,container_spec.copy(),curr_container_resources)
            deploy_spec['match_labels']=container_spec['labels'].copy()
            deployment_obj=create_deployment_object(client,deploy_spec.copy())

            try:
                create_deployment(self.apps_api, deployment_obj,deploy_spec['name'])
            except Exception as e:
                LOGGER.info(f"[FAILURE]: Failed to create deployment {deploy_spec['name']} CAUSE: {e}")
                pass
                #print(f"Could not create deployment {deploy_spec['name']}")
            LOGGER.info(f"[INFO]: Created deployment {deploy_spec['name']}")
            self.deployments[location]=deploy_spec['name']

            service_spec['selector']=container_spec['labels'].copy()
            service_spec['name']=self.app+"-"+location
            service_spec['load_balancer_ip']=self.locations[location]['load_balancer_ip']
            service_spec['port']=self.locations[location]['svc-port']

            try:
                create_service(client,self.core_api,service_spec.copy())
            except Exception as e:
                LOGGER.info(f"[FAILURE]: Failed to create service {service_spec['name']} CAUSE: {e}")
            LOGGER.info(f"[INFO]: Created service {service_spec['name']}")
            self.services[location]=service_spec['name']
        LOGGER.info(f"------------------- Setup Completed------------------")
        self.get_location_info()
        return

    def patch_setup(self,server_deployments):
        #update_deployment(self.apps_api,'kiwix-serve-ap-southeast-2')
        LOGGER.info(f"------------------- Patching Started------------------")
        print(server_deployments)
        for deployment in self.apps_api.list_namespaced_deployment(namespace='default').items:
            if self.app in deployment.metadata.name:
                n_servers=[server_deployments[region] for region in server_deployments.keys() if region in deployment.metadata.name][0]
                curr_container_resources=self.calculate_resources(n_servers)
                update_deployment(self.apps_api,deployment.metadata.name,curr_container_resources)
        return


    def teardown_setup(self):

        LOGGER.info(f"------------------- Teardown Started------------------")
        for deployment in self.apps_api.list_namespaced_deployment(namespace='default').items:
            if self.app in deployment.metadata.name:
                LOGGER.info(f"[INFO] Tearing down deployment {deployment.metadata.name}")
                delete_deployment(client,self.apps_api,deployment.metadata.name)
                if deployment.metadata.name in self.deployments:
                    del self.deployments[deployment.metadata.name]

        for service in self.core_api.list_namespaced_service(namespace='default').items:
            if self.app in service.metadata.name:
                LOGGER.info(f"[INFO] Tearing down service {service.metadata.name}")
                delete_service(client,self.core_api,service.metadata.name)
                if service.metadata.name in self.services:
                    del self.services[service.metadata.name]
        
        #Delete secret
        try:
            api_response = self.core_api.delete_namespaced_secret(secret_name, "default", body=client.V1Secret())
        except:
            pass
        LOGGER.info(f"------------------- Teardown completed------------------")
        return

def main():

    deploy_obj=Deployer()
    #deploy_obj.label_nodes()
    #deploy_obj.patch_setup(server_deployments)
    deploy_obj.teardown_setup()


if __name__ == "__main__":
    main()

