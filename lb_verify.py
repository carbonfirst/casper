import requests

lb_backend="http://192.168.245.71:3001"
region_info= { 'eu-central-1':{'backend_ip':'192.168.245.71','backend_port':31997},
            'eu-west-3':{'backend_ip':'192.168.245.71','backend_port':30543},
            'us-east-1':{'backend_ip':'192.168.245.74','backend_port':31159},
            'us-east-2':{'backend_ip':'192.168.245.74','backend_port':32535},
            'us-west-1':{'backend_ip':'192.168.245.75','backend_port':31930},
            'ap-southeast-2':{'backend_ip':'192.168.245.75','backend_port':30738}}
config_file="/nfs/obelix/users2/sjasoria/kasper/CAP/current_requests.pickle"
regions_list=['ap-southeast-2','eu-central-1','eu-west-3','us-east-1','us-east-2','us-west-1']

if __name__ == "__main__":
    # Get the weights from the load balancer
    response = requests.get(f"{lb_backend}/servers/sample/stats")
    backend_stats=dict()
    resp_json = response.json()
    
    for backend in resp_json["backends"]:
        print(backend)

    with open(config_file, 'rb') as f:
        serialized_weights = f.read()
    # Deserialize the array using pickle
    weights = pickle.loads(serialized_weights)
    # Order of regions: ([Region(ap-southeast-2), Region(eu-central-1), Region(eu-west-3), Region(us-east-1), Region(us-east-2), Region(us-west-1)])
    regionwise_weights = {region:weights[i] for i,region in enumerate(regions_list)}

    # 42724


      ap-southeast-2 eu-central-1 eu-west-3 us-east-1 us-east-2 us-west-1
0           2370        15000      6930      6720      1680      1500
1           2370        15000      6930      6720      1680      1500
  ap-southeast-2 eu-central-1 eu-west-3 us-east-1 us-east-2 us-west-1
0           2093            0     22334      8375         0      1395
1           2093            0     22334      8375         0      1395

136634