# Authors: Basundhara Chakrabarty, Shruti Jasoria

import numpy as np
from .config import Config
from .region import Region
from .util import Util


class Server:
    """An artificial server with a carbon trace, latency and capacity.

    NOTE:
    In-place order used often which refers to the inherent order of regions, e.g. [cali, texas, ...]
    which works as the same order is used everywhere.

    """

    def __init__(self, capacity: int, region: Region):
        """

        Args:
            capacity: A servers capacity, typically same among all servers
            region: Region server is assigned to
            utilization : Computing units utilized in server. Same unit as capacity.
        """
        self.capacity = capacity
        self.utilization = 0
        self.region = region

    def __repr__(self) -> str:
        return f"Server({self.region}, capacity={self.capacity}, utilization={self.utilization})"

    def utilization_left(self):
        """
        Returns:
            Utilization left for a server
        """
        return self.capacity - self.utilization

    def push(self, load):
        """Push batch of requests to buffer. Remove when batch is completed

        Args:
            load: Load of a batch of requests
        """
        assert self.utilization + load <= self.capacity, (
            self.utilization + load,
            self.capacity,
        )

        self.utilization += load

    def reset_utilization(self):
        """Resets the utilization of utilization if restarting simulation. Not applied."""
        self.utilization = 0


class ServerManager:
    """Central manager keeping check of all regions and servers, handles request sourcing to servers etc."""

    def __init__(self, regions=None):
        """

        Args:
            regions: Only set to not None if running tests. Defaults to None.
            servers: List of server objects
        """
        self.region_names = Util.region_names()
        if regions is None:
            self.regions = Region.load_regions()
        else:
            self.regions = regions
        self.servers = []

    def get_region_by_name(self, name):
        """
        Args:
            name: Name of region

        Returns:
            Region object
        """
        for region in self.regions:
            if region.name == name:
                return region
        raise ValueError(f"Region {name} not found")

    def reset(self):
        """
        Reset utilization for every server
        """
        for server in self.servers:
            server.reset_utilization()

    def utilization_left_regions(self):
        """Iterates servers and utilization of their respective region

        Returns:
            List of utilization of all regions, in-place order
        """
        utilization_left = {region: 0 for region in self.region_names}

        for server in self.servers:
            utilization_left[server.region.name] += server.utilization_left()
        return [utilization_left[region] for region in self.region_names]

    def servers_per_region(self):
        """

        Returns:
            Number of servers in each region, in-place order
        """
        count = {region: 0 for region in self.region_names}

        for server in self.servers:
            count[server.region.name] += 1
        return [count[region] for region in self.region_names]

    def capacity_per_region(self):
        """Calculates the regional capacity using a static integer set in runtime configurations.

        Returns:
            Regional capacity, in-place order
        """
        servers = np.array(self.servers_per_region())
        return servers * Config.SERVER_CAPACITY

    def send(self, requests_per_region):
        """Distributes requests to each server for each region

        Args:
            requests_per_region: the n.o. requests to be distributed across servers in a region, in-place.
        """
        utilization_left = self.utilization_left_regions()
        print("Utilization Left: ", utilization_left)
        for i in range(len(self.region_names)):
            region = self.region_names[i]
            # All requests to a {region}
            requests = sum(requests_per_region[:, i])
            # All servers in the {region} we should send our request batches
            servers = [s for s in self.servers if s.region.name == region]
            # Craete request batches that are destined to {region}
            server_loads = self.build_server_loads(servers, requests)

            for server, load in server_loads:
                server.push(load)

    def build_server_loads(self, servers, requests):
        """Places load from requests at servers. The servers are region-specific.

        Args:
            servers: All servers for a region where load is to be placed
            requests: Number of requests sent to a region. NOTE that load of request is 1 unit.

        Returns:
            List of (server, load) for servers in region with their respective load
        """
        initial_requests = requests
        loads = []
        for server in servers:
            left = server.utilization_left()
            load = min(left, requests)
            requests -= load
            assert requests >= 0, requests
            loads.append((server, load))

        if requests > 0:
            print(
                f"Dropping requests: {requests}, initially: {initial_requests}, server_length: {len(servers)}"
            )

        return loads

    def move(self, servers_per_region):
        """Moves the minimum amount of servers to satisfy the number of requests per region

        Args:
            servers_per_region: Specifies the number of servers per region
        """
        count = {region: 0 for region in self.region_names}

        for server in self.servers:
            count[server.region.name] += 1

        # self.servers = []
        # for region, requested_count in zip(self.regions, servers_per_region):
        #     for _ in range(requested_count):
        #         server = Server(self.conf.server_capacity, region)
        #         self.servers.append(server)

        # Remove all abundant servers in each region
        for region_name, requested_count in zip(self.region_names, servers_per_region):
            if count[region_name] > requested_count:
                indices = [i for i, s in enumerate(self.servers) if s.region.name == region_name]
                n = count[region_name] - requested_count
                assert n >= 0, n
                assert n <= len(indices), (n, len(indices))
                for i in range(n - 1, -1, -1):
                    index = indices[i]
                    self.servers.pop(index)

        # Add servers to each region to satisfy the new server per region constraint
        for region, requested_count in zip(self.regions, servers_per_region):
            c = count[region.name]
            while c < requested_count:
                # TODO: Set server capacity in a more generic way
                server = Server(Config.SERVER_CAPACITY, region)
                self.servers.append(server)
                c += 1
            count[region.name] = c

        for region, requested_count in zip(self.regions, servers_per_region):
            s = sum([1 for s in self.servers if s.region.name == region.name])
            assert s == requested_count, (s, requested_count, region)
