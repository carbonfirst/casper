# Authors: Basundhara Chakrabarty, Shruti Jasoria

import math

import numpy as np
from .util import Util


class Region:
    """
    Region object to hold and get region-specific data.
    """

    def __init__(self, name, carbon_intensity,carbon_cost_estimate_per_srv, request, latency, offset) -> None:
        self.name = name
        self.request = request
        self.carbon_intensity = carbon_intensity
        self.carbon_cost_estimate_per_srv=carbon_cost_estimate_per_srv
        self._latency = latency
        self.offset = offset
        self.region_names = Util.region_names()
        self.exponential_df = None

    def __repr__(self):
        return f"Region({self.name})"

    def __format__(self, __format_spec: str) -> str:
        return format(self.name, __format_spec)

    def get_requests_per_interval(self, hour):
        # print("self.request.iloc[hour][self.region_names].sum()",self.request.iloc[hour][self.region_names].sum())
        #print("self.request.iloc[hour][self.name]",self.name,self.request.iloc[hour][self.name])
        return self.request.iloc[hour][self.name]

    def get_expo_requests_per_interval(self, t):
        return self.exponential_df.iloc[t][self.name]
    
    def get_requests_per_interval_per_region(self, t):
        return self.request.iloc[t][self.region_names].to_numpy(dtype=np.float64)

    def latency(self, region):
        assert isinstance(region, Region)
        #print(self._latency.head)
        return self._latency[region.name]

    def haversine_latency(self, other):
        """
            Uses the haversine distance d [km] between two points
            and calculates latency as L=0.022*0.62*d+m [ms].

            TODO: Add random fluctuations sd=2.5 ms ?
        Args:
            other: The other region we want to calculate distance to
        """
        assert isinstance(other, Region)

        lat1 = self.location[0] * math.pi / 180
        lat2 = other.location[0] * math.pi / 180
        dlat = lat2 - lat1
        dlon = (other.location[1] - self.location[1]) * math.pi / 180

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        d = 6371 * c

        return 0.022 * 0.62 * d + 4.862

    @staticmethod
    def load_regions():
        """Loads data for all regions from csv files and returns all regions

        Returns:
            List of all region objects containing their specific data
        """
        regions = []

        offset_df = Util.load_offset_from_file()
        # TODO - make changes to this method
        latency_df = Util.load_latency_from_file()
        request_df = Util.load_request_from_file()
        carbon_intensity_df = Util.load_carbon_intensity_from_file()
        #print("Latency:",latency_df.head)

        for region in Util.region_names():
            latency = latency_df[region]
            carbon_intensity = carbon_intensity_df[region]
            carbon_cost_estimate_per_srv=carbon_intensity.mean(axis=0)
            #print("carbon_cost_estimate_per_srv: {0} ;  region:{1} ".format(region,carbon_cost_estimate_per_srv))
            offset = offset_df[region].values[0]
            region = Region(region, carbon_intensity, carbon_cost_estimate_per_srv, request_df, latency, offset)
            #print("Built region: ",region)
            regions.append(region)
        return regions
