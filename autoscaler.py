# Autoscaler that monitors the CPU/Memory stats of the deployment and adds resources whereever necessary

import utils
from kubernetes import client, config
import time
import re

namespace = "default"
deployments_locations={'us-central':'kiwix-serve-us-central','us-east':'kiwix-serve-us-east','us-west':'kiwix-serve-us-west'}

def get_stats_by_location(custom_obj_api,apps_api):
    
    container_resources=utils.get_resources()
    print("container_resources",container_resources)

    response = custom_obj_api.list_cluster_custom_object(
        "metrics.k8s.io", "v1beta1", "pods"
        )
    for pod in response['items']:
        pod_name = pod['metadata']['name']
        if "kiwix-serve" not in pod_name:
            continue
        pod_location=pod['metadata']['labels']['location']
        pod_deployment=deployments_locations[pod_location]
        pod_total_memory=0.0
        pod_total_cpu=0.0
        for container in pod['containers']:
            cpu=container['usage']['cpu']
            pod_total_cpu=utils.sum_cpu(str(pod_total_cpu),cpu)
            memory=container['usage']['memory']
            pod_total_memory=utils.sum_memory(str(pod_total_memory),memory)
        
        
        cpu_cutoff = 0.9*float(container_resources['cpu']['limit'])
        if (pod_total_cpu >= cpu_cutoff):
            print("\nEXCEEDED!")
            print(f'Pod Name:{pod_name}\tLocation:{pod_location}\tDeployment:{pod_deployment}\tCPU Usage:{pod_total_cpu}\tCPU Limit:{cpu_cutoff}')
            utils.update_deployment(apps_api,pod_deployment)
        print(f'Pod Name:{pod_name}\tLocation:{pod_location}\tDeployment:{pod_deployment}\tCPU:{pod_total_cpu}\tMemory:{pod_total_memory}')
        print("container_resources",container_resources)
    return

def main():
    config.load_kube_config()
    custom_obj_api = client.CustomObjectsApi()
    apps_api = client.AppsV1Api()
    

    while(True):
        get_stats_by_location(custom_obj_api,apps_api)
        time.sleep(10)


if __name__ == "__main__":
    main()
