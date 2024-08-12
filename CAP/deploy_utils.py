import re
import os
import base64
import json
import copy

container_resources_bak={'cpu':{'requested':"0.01","limit":"0.1"},'memory':{'requested':"100M","limit":"400M"}}

def split_num_unit(amt):
    num=float(re.findall('^[-+]?[0-9]*\.?[0-9]+', amt)[0])
    unit1=re.findall('[A-Za-z]+',amt)
    unit=unit1[0] if len(unit1)!=0 else ''
    return num,unit

# Function that takes in two values for cpu usage, adds them and returns the summed cpu usage.
def sum_cpu(amt1,amt2):
    multiplier={'m':0.001,'n':0.000000001,'':1.0}
    unit=['a']*2
    num1,unit[0]=split_num_unit(amt1)
    num2,unit[1]=split_num_unit(amt2)
    if unit[0] not in multiplier or unit[1] not in multiplier:
            raise Exception(f"Units is not identified: Check the units: {unit[0]}, {unit[1]}")
    
    total_cpu=num1*multiplier[unit[0]]+num2*multiplier[unit[1]]
    return total_cpu

# Function that takes in two values for memory usage, adds them and returns the summed memory usage.
def sum_memory(amt1,amt2):
    multiplier={'M':1.0,'Ki':0.001,'':1.0}
    unit=['a']*2
    num1,unit[0]=split_num_unit(amt1)
    num2,unit[1]=split_num_unit(amt2)
    if unit[0] not in multiplier or unit[1] not in multiplier:
            raise Exception(f"Units is not identified: Check the units: {unit[0]}, {unit[1]}")
    
    return num1*multiplier[unit[0]]+num2*multiplier[unit[1]]

def get_resources():
    new_container_resources=copy.deepcopy(container_resources)
    for key in new_container_resources['memory']:
        new_container_resources['memory'][key]=float(re.findall('^[-+]?[0-9]*\.?[0-9]+', new_container_resources['memory'][key])[0])
    return new_container_resources

def create_kube_secret(client,core_api,registry,cred_name):
    # Create the Kubernetes secret object
    dockerconfig = {
        "auths": {
                    registry["registry"]: {
                        "username": registry["username"],
                        "password": registry["password"],
                        "email": registry["email"],
                        "auth": ""
                        }
                    }
                }
    data = {
                ".dockerconfigjson": base64.b64encode(
                    json.dumps(dockerconfig).encode()
                ).decode()
            }
    secret = client.V1Secret(
                            api_version="v1",
                            data=data,
                            kind="Secret",
                            metadata=dict(name=cred_name, namespace="default"),
                            type="kubernetes.io/dockerconfigjson",
                        )
    core_api.create_namespaced_secret(namespace="default", body=secret)
    return






#Backup deployment function for httpd
def create_deployment_object_bak(client,deployment_name):
    # Configureate Pod template container
    containers=[]
    container = client.V1Container(
        name="httpd",
        image="httpd:latest",
        ports=[client.V1ContainerPort(container_port=80)],
        resources=client.V1ResourceRequirements(
            requests={"cpu": container_resources['cpu']['requested'], "memory": container_resources['memory']['requested']},
            limits={"cpu": container_resources['cpu']['limit'], "memory": container_resources['memory']['limit']},
        ),
    )
    containers.append(container)

    # Create and configure a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={'app':'httpd'},namespace='default'),
        spec=client.V1PodSpec(containers=containers,node_selector={'location':'us-west'}),
    )

    # Create the specification of deployment
    spec = client.V1DeploymentSpec(
        replicas=1, template=template,
        selector=client.V1LabelSelector(match_labels={'app':'httpd'}))

    # Instantiate the deployment object
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=deployment_name,namespace='default'),
        spec=spec,
    )

    return deployment

#container_spec={'name':'kiwix-serve','image':'kiwix/kiwix-serve:latest",'command':["/usr/bin/kiwix-serve", "wikipedia_en_top_maxi_2021-08.zim"],'n_containers':1,'labels':{'app':'httpd'},'node_selector':{'location':'us-west'},'container_port':80,'host_port':8081}
def create_pod_template(client,container_spec,container_resources):

    containers=list()
    for n in range(container_spec['n_containers']):
        container = client.V1Container(
                                        name=container_spec['name'],
                                        image=container_spec['image'],
                                        image_pull_policy= 'IfNotPresent',
                                        #command=['/usr/local/bin/kiwix-serve', '--port=8080', '--library', '/data/library.xml'],
                                        # volume_mounts=[client.V1VolumeMount(
                                        #     name="shared-kiwix-data",
                                        #     mount_path="/data",
                                        # )],
                                        ports=[client.V1ContainerPort(container_port=container_spec['container_port'])],
                                                                    #host_ip="127.0.0.1",
                                                                    #host_port=container_spec['host_port'])],
                                        resources=client.V1ResourceRequirements(
                                            requests={"cpu": container_resources['cpu']['requested'], 
                                            "memory": container_resources['memory']['requested']},
                                            limits={"cpu": container_resources['cpu']['limit'], 
                                            "memory": container_resources['memory']['limit']},
                                        ),
        )
        containers.append(container)

    # Create and configure a spec section
    curr_dir=os.getcwd()
    print("Curr directory",curr_dir)
    volume_dir=curr_dir+'/zim'
    print("Volume directory",volume_dir)
    pod_template = client.V1PodTemplateSpec(
                                metadata=client.V1ObjectMeta(labels=container_spec['labels'],
                                    namespace='default'),
                                spec=client.V1PodSpec(
                                        containers=containers,
                                        image_pull_secrets=[client.V1LocalObjectReference(name="regcred")],
                                        # volumes=[client.V1Volume(
                                        #     name="shared-kiwix-data",
                                        #     host_path=client.V1HostPathVolumeSource(path=volume_dir,
                                        #     type= "DirectoryOrCreate")
                                        # )],
                                        node_selector=container_spec['node_selector']
                                        )
                                )
    return pod_template

#deploy_spec={'name':'kiwix-serve','pod-template':pod_template,'match_labels':{"app": "kiwix-serve"},'n_replicas':'600'}
def create_deployment_object(client,deploy_spec):

    # Instantiate the deployment object
    deployment_obj = client.V1Deployment(
                                        api_version="apps/v1",
                                        kind="Deployment",
                                        metadata=client.V1ObjectMeta(name=deploy_spec['name'],namespace='default'),
                                        spec=client.V1DeploymentSpec(
                                            replicas=deploy_spec['n_replicas'], 
                                            template=deploy_spec['pod_template'],
                                            selector=client.V1LabelSelector(match_labels=deploy_spec['match_labels'])
                                        ),
                                    )
    return deployment_obj

#api = client.AppsV1Api()
def create_deployment(api, deployment_obj,deployment_name):
    # Create deployment
    resp = api.create_namespaced_deployment(
        body=deployment_obj, namespace="default"
    )

    print(f"\n[INFO] deployment `{deployment_name}` created.\n")
    print("%s\t%s\t\t\t%s\t%s" % ("NAMESPACE", "NAME", "REVISION", "IMAGE"))
    print(
        "%s\t\t%s\t%s\t\t%s\n"
        % (
            resp.metadata.namespace,
            resp.metadata.name,
            resp.metadata.generation,
            resp.spec.template.spec.containers[0].image,
        )
    )
    return

# client.AppsV1Api()
def get_deployment_by_name(api,deployment_name):
    for item in api.list_namespaced_deployment(namespace='default').items:
        if item.metadata.name==deployment_name:
            return item
    raise ValueError("Deployment does not exist!") 


#api = client.AppsV1Api()
def update_deployment(api,deployment_name,container_resources):
    # Update container image
    deployment=None
    try:
        deployment=get_deployment_by_name(api,deployment_name)
    except ValueError:
        print("Deployment does not exist!")
        exit()  

    #print(deployment.spec)
    for container in deployment.spec.template.spec.containers:
        container.resources.requests["cpu"]=container_resources['cpu']['requested']
        container.resources.limits["cpu"]=container_resources['cpu']['limit']

    # patch the deployment
    resp = api.patch_namespaced_deployment(
        name=deployment_name, namespace="default", body=deployment
    )

    print(f"\n[INFO] Verifying update: CPU Limit: {deployment.spec.template.spec.containers[0].resources.limits['cpu']}\n")
    return

def delete_deployment(client,api,deployment_name):
    # Delete deployment
    resp = api.delete_namespaced_deployment(
        name=deployment_name,
        namespace="default",
        body=client.V1DeleteOptions(
            propagation_policy="Foreground", grace_period_seconds=5
        ),
    )
    print(f"\n[INFO] deployment {deployment_name} deleted.")
    return

# service_specs={'type':'LoadBalancer','selector':{"app": "kiwix-serve"},'name':'load-balancer','port':<port>}
def create_service(client,core_api,service_specs):

    spec=client.V1ServiceSpec(
        type=service_specs['type'],
        load_balancer_ip=service_specs['load_balancer_ip'],
        selector=service_specs['selector'],
        ports=[client.V1ServicePort(
            name="http",
            port=service_specs['port'],
            target_port=8080
        )] 
        )
    service = client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(   name=service_specs["name"],
                                        annotations={"metallb.universe.tf/allow-shared-ip": "kiwix-serve"},
                                        namespace="default"),
        spec=spec
    )

    core_api.create_namespaced_service(namespace="default", body=service)

    return service

def delete_service(client,core_api,service_name):
    # Delete the service
    response = core_api.delete_namespaced_service(
        name=service_name, namespace="default",
        body=client.V1DeleteOptions(
            propagation_policy='Foreground',
            grace_period_seconds=5
        )
    )
    return

def create_pod(client,api,pod_name,location):
    containers=[]
    container = client.V1Container(
        name="nginx",
        image="nginx:1.15.4",
        ports=[client.V1ContainerPort(container_port=80)],
        resources=client.V1ResourceRequirements(
            requests={"cpu": "100m", "memory": "100Mi"},
            limits={"cpu": "200m", "memory": "200Mi"},
        ),
    )
    containers.append(container)
    node_selector={'location':location}

    pod_spec = client.V1PodSpec(containers=containers,node_selector=node_selector)
    pod_metadata = client.V1ObjectMeta(name=pod_name, namespace="default")

    pod_body = client.V1Pod(api_version="v1", kind="Pod", metadata=pod_metadata, spec=pod_spec)
        
    pod=api.create_namespaced_pod(namespace="default", body=pod_body)
    return pod