#!/usr/bin/env python3

import json
import pickle
import numpy as np

# Sample request redirection matrix and servers matrix
# [[2236    0    0    0    0    0]
#  [   0 8173 4157    0    0    0]
#  [   0    0 5843    0    0    0]
#  [   0    0    0 5798    0    0]
#  [   0    0    0 1500    0    0]
#  [   0    0    0    0    0 1331]] [ 3  9 10  8  0  2]

#requests=[[2236,0,0,0,0,0],[0,8173,4157,0,0,0],[0,0,5843,0,0,0],[0,0,0,5798,0,0],[0,0,0,1500,0,0],[0,0,0,0,0,1331]]
# servers=[3,9,10,8,0,2]

config_file="/nfs/obelix/users2/sjasoria/kasper/CAP/current_requests.pickle"

# Use this code on CAP to save the serialized requests array to the shared config file
# To dump the requests array to the shared config file
# serialized_array = pickle.dumps(requests)

# with open(config_file, 'wb') as f:
#     f.write(serialized_array)

# Load the serialized array from the file
with open(config_file, 'rb') as f:
    serialized_weights = f.read()

# Deserialize the array using pickle
weights = pickle.loads(serialized_weights)

#print(weights)
# Perform discovery logic to determine backend endpoints
# Order of regions: ([Region(ap-southeast-2), Region(eu-central-1), Region(eu-west-3), Region(us-east-1), Region(us-east-2), Region(us-west-1)])
endpoints = [
    {"host": "192.168.245.75", "port": 30738, "weight":1},
    {"host": "192.168.245.71", "port": 31997, "weight":1},
    {"host": "192.168.245.71", "port": 30543, "weight":1},
    {"host": "192.168.245.74", "port": 31159, "weight":1},
    {"host": "192.168.245.74", "port": 32535, "weight":1},
    {"host": "192.168.245.75", "port": 31930, "weight":1}
]

#Print the endpoints to stdout in JSON format
for endpoint,weight in zip(endpoints,weights):
    endpoint['weight']= int(weight)
    #print(endpoint)
    print(f"{endpoint['host']}:{endpoint['port']} weight={endpoint['weight']}")

