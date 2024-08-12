import pandas as pd
from prometheus_api_client import PrometheusConnect
import logging
import requests
import numpy as np

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()])

LOGGER = logging.getLogger(__name__)

class Metrics:
    def __init__(self) -> None:
        """
        Initializes the metrics class
        """

        # Regions are ['ap-southeast-2', 'eu-central-1', 'eu-west-3', 'us-east-1', 'us-east-2','us-west-1':1]
        self.region_list=['ap-southeast-2', 'eu-central-1', 'eu-west-3', 'us-east-1', 'us-east-2','us-west-1']

        # The traeffik metrics server and ports mapped to each region's trafik instance
        self.traefik_metrics_srv='192.168.245.71'
        self.traefik_metrics_ports= {'ap-southeast-2':4001, 'eu-central-1':4002, 'eu-west-3':4003, 'us-east-1':4004, 'us-east-2':4005,'us-west-1':4006}

        # The prometheus server and client to run promestheus queries
        self.promestheus_url = "http://192.168.245.71:9090"
        self.prom_client=PrometheusConnect(url=self.promestheus_url, disable_ssl=True)

        # The promestheus metrics that shall be collected

        # served_requests: n*n dataframe where df[i,j] is the number of requests arriving at load balancer of region i but successfully served by region j
        self.served_requests=pd.DataFrame(0,columns=self.region_list, index=self.region_list).astype(int)
        # failed_requests: n*n dataframe where df[i,j] is the number of requests arriving at load balancer of region i and supposed to be served by region j but failed
        self.failed_requests=pd.DataFrame(0,columns=self.region_list, index=self.region_list).astype(int)
        # request_service_time: n*n dataframe where df[i,j] is the average service time of requests arriving at load balancer of region i and served by region j
        self.request_service_time_sum=pd.DataFrame(0,columns=self.region_list, index=self.region_list).astype(float)
        self.request_service_time_count=pd.DataFrame(0,columns=self.region_list, index=self.region_list).astype(float)
        self.avg_request_service_time= pd.DataFrame(0,columns=self.region_list, index=self.region_list).astype(float)
        return

    # Sample output of served_requests dataframe
    #                     ap-southeast-2  eu-central-1  eu-west-3  us-east-1  us-east-2  us-west-1
    # ap-southeast-2               0             0          0          1          0          0
    # eu-central-1                 1             1          1          1          1          0
    # eu-west-3                    0             0          1          0          0          1
    # us-east-1                    0             0          0          0          0          0
    # us-east-2                    1             0          0          0          0          1
    # us-west-1                    0             0          0          0          1          0
    def fill_served_requests(self):
        """
        Fills the served_requests dataframe with the number of requests served by each region
        """

        print(self.served_requests)
        LOGGER.info("[INFO] Getting metric: Number of successful HTTP requests served by region")
        metric='traefik_service_requests_total'
        # For each origin region and each destination region, get the count of successful HTTP GET requests, i.e. code=200, method=GET
        for from_region in self.region_list:
            instance=f"{self.traefik_metrics_srv}:{self.traefik_metrics_ports[from_region]}"
            for to_region in self.region_list:
                label_config = {'instance': instance, 'code': '200', 'method': 'GET', 'service': f'{to_region}@file'}
                result = self.prom_client.get_current_metric_value(metric,label_config=label_config)
                if len(result) > 0:
                    # LOGGER.info(f"[INFO] Number of successful HTTP requests from region {from_region} served by {to_region}: {result[0]['value'][1]}")
                    self.served_requests.loc[from_region,to_region]=int(result[0]['value'][1])
                else:
                    pass
                    # LOGGER.info(f"[INFO] Number of successful HTTP requests from region {from_region} served by {to_region}: 0! Skipping request count calculation")
        LOGGER.info('[INFO] Number of successful HTTP requests served by region')
        print(self.served_requests)
        return

    

    def fill_request_service_time(self):
        """
        Fills the request_service_time dataframe with the average service time of requests served by each region. This is obtained by dividing the sum of the request service times by the number of requests for each (origin, destination) pair
        """
        request_service_time_sum=pd.DataFrame(0.0,columns=self.region_list, index=self.region_list).astype(float)
        request_service_time_count=pd.DataFrame(0.0,columns=self.region_list, index=self.region_list).astype(float)

        LOGGER.info("[INFO] Getting metric: Request service time by region")
        # request_duration_sum_metric: Sum of the request service times for all requests from region i but served in region j
        request_duration_sum_metric="traefik_service_request_duration_seconds_sum"
        # request_duration_sum_metric: Count of the service requests for all requests from region i but served in region j (both successful and failed)
        request_duration_count_metric="traefik_service_request_duration_seconds_count"

        for from_region in self.region_list:
            instance=f"{self.traefik_metrics_srv}:{self.traefik_metrics_ports[from_region]}"
            for to_region in self.region_list:
                label_config = {'instance': instance,'code': '200', 'method': 'GET', 'service': f'{to_region}@file'}
                time_sum = self.prom_client.get_current_metric_value(request_duration_sum_metric,label_config=label_config)
                if len(time_sum) > 0:
                    # LOGGER.info(f"[INFO] Sum of request service times from region {from_region} served by {to_region}: {time_sum[0]['value'][1]}")
                    time_count = self.prom_client.get_current_metric_value(request_duration_count_metric,label_config=label_config)
                    # LOGGER.info(f"[INFO] Count of requests from region {from_region} served by {to_region}: {time_count[0]['value'][1]}")
                    self.request_service_time_sum.loc[from_region,to_region]=float(time_sum[0]['value'][1])
                    self.request_service_time_count.loc[from_region,to_region]=float(time_count[0]['value'][1])
                else:
                    pass
                    # LOGGER.info(f"[INFO] Count of requests times from region {from_region} served by {to_region}: 0. Skipping response time calculation")
        LOGGER.info('[INFO] Sum of request service times by region')
        print(self.request_service_time_sum)
        LOGGER.info('[INFO] Count of request service times by region')
        print(self.request_service_time_count)    
        return

    # The stats can be deleted by running the POST request: curl -X POST -g 'http://localhost:9090/api/v1/admin/tsdb/delete_series?match[]=traefik_service_requests_total{job="prometheus"}'
    def reset_promestheus_stats(self):
        """
        Resets the prometheus stats for all regions
        """

        LOGGER.info("[INFO] Resetting prometheus stats for all regions")
        url = f"{self.promestheus_url}/api/v1/admin/tsdb/delete_series"
        params = {"match[]": "traefik_service_requests_total{job=\"prometheus\"}"}
        response = requests.post(url, params=params)
        LOGGER.info(f"[INFO] Prometheus stats reset completed with status code: {response.status_code} and message: {response.text}")

        return

    def get_relevant_metrics(self):
        """
        Calculates the the relevant metrics from class variables and returns them
        """
        # Calculate the necessary metrics
        self.fill_served_requests()
        self.fill_request_service_time()

        # Calculate the total number of requests coming from each region
        requests_from_total= self.served_requests.sum(axis=1)

        # Calculate the total number of requests destined to each region
        requests_to_total= self.served_requests.sum(axis=0)

        # Each value of request_duration_sum_metric= avg service duration of one request * number of requests
        # Therefore, the avg service time at each region is the sum of the service times of all requests divided by the total number of requests
        weighted_avg = (self.request_service_time_sum * 1000) /  self.request_service_time_count
        print("weighted_avg",weighted_avg)
        self.avg_request_service_time = weighted_avg.fillna(np.finfo(float).eps)
        return requests_from_total,requests_to_total, self.avg_request_service_time

        

if __name__ == "__main__":
    obj=Metrics()
    obj.fill_served_requests()
    #obj.fill_served_requests()
    # requests_from_total,requests_to_total, avg_request_service_time=obj.get_relevant_metrics()
    # total=  pd.Series(0, index=obj.region_list)
    # total=total+requests_to_total
    # print(total)
    # global_requests_to_df = pd.DataFrame(columns=obj.region_list)
    # global_requests_to_df=global_requests_to_df.append(total, ignore_index=True)
    # print(global_requests_to_df)



# TRAEFIK METRICS
# traefik_config_last_reload_failure
# traefik_config_last_reload_success
# traefik_config_reloads_failure_total
# traefik_config_reloads_total
# traefik_entrypoint_open_connections
# traefik_entrypoint_request_duration_seconds_bucket
# traefik_entrypoint_request_duration_seconds_count
# traefik_entrypoint_request_duration_seconds_sum
# traefik_entrypoint_requests_bytes_total
# traefik_entrypoint_requests_total
# traefik_entrypoint_responses_bytes_total
# traefik_router_open_connections
# traefik_router_request_duration_seconds_bucket
# traefik_router_request_duration_seconds_count
# traefik_router_request_duration_seconds_sum
# traefik_router_requests_bytes_total
# traefik_router_requests_total
# traefik_router_responses_bytes_total
# traefik_service_open_connections
# traefik_service_request_duration_seconds_bucket
# traefik_service_request_duration_seconds_count
# traefik_service_request_duration_seconds_sum
# traefik_service_requests_bytes_total
# traefik_service_requests_total
# traefik_service_responses_bytes_total


