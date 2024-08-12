from kubernetes import client, config, watch
import utils
import logging
import copy

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
        self.locations= {'eu-central-1':{'replicas':1,'svc-port':8081,'load_balancer_ip':'192.168.245.71'},
                    'eu-west-3':{'replicas':1,'svc-port':8082,'load_balancer_ip':'192.168.245.71'},
                    'us-east-1':{'replicas':1,'svc-port':8083,'load_balancer_ip':'192.168.245.74'},
                    'us-east-2':{'replicas':1,'svc-port':8084,'load_balancer_ip':'192.168.245.74'},
                    'us-west-1':{'replicas':1,'svc-port':8085,'load_balancer_ip':'192.168.245.75'},
                    'ap-southeast-2':{'replicas':1,'svc-port':8086,'load_balancer_ip':'192.168.245.75'}}
        self.app='kiwix-serve'
        self.secret_name="regcred"
        self.cpu_per_server=0.01
        self.cpu_epsilon=0.001
        self.container_resources={'cpu':{'requested':"0.01","limit":"0.1"},'memory':{'requested':"100M","limit":"400M"}}
        self.region_list=list(self.locations.keys())
        self.services=dict()
        self.deployments=dict()
        self.server_regions_map={region:1 for region in self.region_list}

    #Labels each node with the app name, and by each location provided
    def label_nodes(self,):
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
                    "username": "casperumass",
                    "password": "dckr_pat_S1IeaRVaExnJfJTFJRcxu4TbVp8",
                    "email": "bchakrabarty@umass.edu",
                    "registry": "https://index.docker.io/v1/"
                    }

        LOGGER.info(f"------------------- Setup Started------------------")
        #Create the secret to pull the image from DockerHub
        try:
            utils.create_kube_secret(client,self.core_api,registry,self.secret_name)
        except:
            pass

        LOGGER.info(f"------------------- Locations: {self.region_list} -------------------")
        for location in self.region_list:
            container_spec['node_selector']={location:'True'}
            container_spec['labels']['location']=location
            deploy_spec['n_replicas']=self.locations[location]['replicas']
            deploy_spec['name']=self.app+"-"+location
            curr_container_resources=self.calculate_resources(server_deployments[location])
            deploy_spec['pod_template']=utils.create_pod_template(client,container_spec.copy(),curr_container_resources)
            deploy_spec['match_labels']=container_spec['labels'].copy()
            deployment_obj=utils.create_deployment_object(client,deploy_spec.copy())

            try:
                utils.create_deployment(self.apps_api, deployment_obj,deploy_spec['name'])
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
                utils.create_service(client,self.core_api,service_spec.copy())
            except Exception as e:
                LOGGER.info(f"[FAILURE]: Failed to create service {service_spec['name']} CAUSE: {e}")
            LOGGER.info(f"[INFO]: Created service {service_spec['name']}")
            self.services[location]=service_spec['name']
        LOGGER.info(f"------------------- Setup Completed------------------")
        return

    def patch_setup(self,server_deployments):
        #utils.update_deployment(self.apps_api,'kiwix-serve-ap-southeast-2')
        LOGGER.info(f"------------------- Patching Started------------------")
        print(server_deployments)
        for deployment in self.apps_api.list_namespaced_deployment(namespace='default').items:
            if self.app in deployment.metadata.name:
                n_servers=[server_deployments[region] for region in server_deployments.keys() if region in deployment.metadata.name][0]
                curr_container_resources=self.calculate_resources(n_servers)
                utils.update_deployment(self.apps_api,deployment.metadata.name,curr_container_resources)
        return


    def teardown_setup(self):

        LOGGER.info(f"------------------- Teardown Started------------------")
        for deployment in self.apps_api.list_namespaced_deployment(namespace='default').items:
            if self.app in deployment.metadata.name:
                LOGGER.info(f"[INFO] Tearing down deployment {deployment.metadata.name}")
                utils.delete_deployment(client,self.apps_api,deployment.metadata.name)
                if deployment.metadata.name in self.deployments:
                    del self.deployments[deployment.metadata.name]

        for service in self.core_api.list_namespaced_service(namespace='default').items:
            if self.app in service.metadata.name:
                LOGGER.info(f"[INFO] Tearing down service {service.metadata.name}")
                utils.delete_service(client,self.core_api,service.metadata.name)
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

