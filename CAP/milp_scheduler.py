# Authors: Basundhara Chakrabarty, Shruti Jasoria

import logging

import numpy as np
import pulp as plp
from .config import Config
from .util import Util


class Latency:
    @staticmethod
    def schedule_servers(
        carbon_intensities,
        latencies,
        capacities,
        request_rates
    ):
        """
        This is the latency greedy scheduler to compare with the Carbon Aware Scheduler. The placement
        of servers are determined by latency rather than by carbon.

        If problem was not solved, a negative objective value is returned

        Args:
            request_rates: request_rates[i] is the number of requests from region i
            capacities: capacities[i] is the average capacity per server in region i
            latencies: latencies[i][j] is the latency from region i to j
            carbon_intensities: carbon_intensities[i] is the carbon intensity in region i
            max_servers: max_servers is the maximum number of servers
            max_latency: max_latency is the maximum latency allowed
        Returns:
            return1: x[i][j] is the number of requests from region i that should
            be sent to region j.
            return2: n_servers[i] is the number of servers that should be started
            in region i.
            return3: objective value.
        """
        opt_model = plp.LpProblem("model",plp.LpMinimize)
        n_regions = len(carbon_intensities)
        max_latency_per_region=[max(row)for row in latencies]
        max_servers=Config.MAX_SERVERS_PER_REGION*n_regions
        alpha=0.5
        #print("sum_request_rate",sum_request_rate,"max_carbon_intensities",max_carbon_intensities,"max_servers",max_servers)

        max_obj_1=1/sum([i*j for i,j in zip(request_rates,max_latency_per_region)])
        print(max_obj_1)

        set_R = range(n_regions)  # Region set
        x_vars = {
            (i, j): plp.LpVariable(cat=plp.LpInteger, lowBound=0, name=f"x_{i}_{j}") for i in set_R for j in set_R
        }

        max_obj_2=1/max_servers
        #max_obj_2=plp.LpVariable(cat=plp.LpInteger, lowBound=max_servers,upBound=max_servers, name="max_servers")
        s_vars = {i: plp.LpVariable(cat=plp.LpInteger, lowBound=0, upBound=Config.MAX_SERVERS_PER_REGION, name=f"s_{i}") for i in set_R}

        # Identify idx of load balancer
        region_names = Util.region_names()
        lb_idx = region_names.to_list().index(Config.LOAD_BALANCER_REGION)


        # Cap the number of servers
        opt_model.addConstraint(
            plp.LpConstraint(
                e=plp.lpSum(s_vars[i] for i in set_R),
                sense=plp.LpConstraintLE,
                rhs=max_servers,
                name="max_server",
            )
        )

        # Per server max capacity
        for j in set_R:
            opt_model.addConstraint(
                plp.LpConstraint(
                    e=plp.lpSum(x_vars[i, j] for i in set_R) - s_vars[j] * capacities[j],
                    sense=plp.LpConstraintLE,
                    rhs=0,
                    name=f"capacity_const{j}",
                )
            )

        # All requests from a region must go somewhere.
        for i in set_R:
            opt_model.addConstraint(
                plp.LpConstraint(
                    e=plp.lpSum(x_vars[i, j] for j in set_R),
                    sense=plp.LpConstraintEQ,
                    rhs=request_rates[i],
                    name=f"sched_all_reqs_const{i}",
                )
            )

        objective = alpha*max_obj_1*plp.lpSum((latencies[i][j]) * x_vars[i, j] for i in set_R for j in set_R)+(1-alpha)*max_obj_2*plp.lpSum(s_vars[i] for i in set_R)

        opt_model.setObjective(objective)
        opt_model.solve(plp.PULP_CBC_CMD(msg=Config.VERBOSE_MILP))

        requests = np.zeros((len(set_R), len(set_R)), dtype=int)
        for i, j in x_vars.keys():
            requests[i, j] = int(x_vars[i, j].varValue)

        servers=np.array([int(s.varValue) for s in s_vars.values()])
        print(requests,servers,objective.value())
        if opt_model.sol_status != 1:
            return np.zeros(n_regions), requests, -10000

        return (
            servers,
            requests,
            objective.value(),
        )

class Carbon:
    @staticmethod
    def schedule_servers(
        carbon_intensities,
        latencies,
        capacities,
        request_rates
    ):
        """
        This is the Carbon Aware Provisioner (CAP) where the placement of servers are determined.
        For example if one region have a low carbon intensity for the next hours, more servers
        should be allocated there.

        If problem was not solved, a negative objective value is returned

        Args:
            request_rates: request_rates[i] is the number of requests from region i
            capacities: capacities[i] is the average capacity per server in region i
            latencies: latencies[i][j] is the latency from region i to j
            carbon_intensities: carbon_intensities[i] is the carbon intensity in region i
        Returns:
            return1: x[i][j] is the number of requests from region i that should
            be sent to region j.
            return2: n_servers[i] is the number of servers that should be started
            in region i.
            return3: objective value.
        """
        opt_model = plp.LpProblem(name="model")
        n_regions = len(carbon_intensities)
        max_carbon_intensities=max(carbon_intensities)
        max_servers=Config.MAX_SERVERS_PER_REGION*n_regions
        max_obj_1=1/sum([max_carbon_intensities*j for j in request_rates])
        max_obj_2=1/max_servers
        alpha=0.9

        # Identify idx of load balancer
        region_names = Util.region_names()
        lb_idx = region_names.to_list().index(Config.LOAD_BALANCER_REGION)

        set_R = range(n_regions)  # Region set
        x_vars = {
            (i, j): plp.LpVariable(cat=plp.LpInteger, lowBound=0, name=f"x_{i}_{j}") for i in set_R for j in set_R
        }
        s_vars = {i: plp.LpVariable(cat=plp.LpInteger, lowBound=0, upBound=Config.MAX_SERVERS_PER_REGION, name=f"s_{i}") for i in set_R}

        # Cap the number of servers
        opt_model.addConstraint(
            plp.LpConstraint(
                e=plp.lpSum(s_vars[i] for i in set_R),
                sense=plp.LpConstraintLE,
                rhs=max_servers,
                name="max_server",
            )
        )

        # Per server max capacity
        for j in set_R:
            opt_model.addConstraint(
                plp.LpConstraint(
                    e=plp.lpSum(x_vars[i, j] for i in set_R) - s_vars[j] * capacities[j],
                    sense=plp.LpConstraintLE,
                    rhs=0,
                    name=f"capacity_const{j}",
                )
            )

        # All requests from a region must go somewhere.
        for i in set_R:
            opt_model.addConstraint(
                plp.LpConstraint(
                    e=plp.lpSum(x_vars[i, j] for j in set_R),
                    sense=plp.LpConstraintEQ,
                    rhs=request_rates[i],
                    name=f"sched_all_reqs_const{i}",
                )
            )

        # Latency constraint
        for i in set_R:
            for j in set_R:
                opt_model.addConstraint(
                    plp.LpConstraint(
                        e=x_vars[i, j] * (latencies[i][j] - Config.MAX_LATENCY),
                        sense=plp.LpConstraintLE,
                        rhs=0,
                        name=f"latency_const{i}_{j}",
                    )
                )

        #objective = plp.lpSum(carbon_intensities[j] * plp.lpSum(x_vars[i, j] for i in set_R) for j in set_R)
        objective = alpha*max_obj_1*plp.lpSum(x_vars[i, j] * carbon_intensities[j] for i in set_R for j in set_R)+(1-alpha)*max_obj_2*plp.lpSum(s_vars[i] for i in set_R)

        opt_model.setObjective(objective)
        opt_model.solve(plp.PULP_CBC_CMD(msg=Config.VERBOSE_MILP))
        requests = np.zeros((len(set_R), len(set_R)), dtype=int)
        for i, j in x_vars.keys():
            requests[i, j] = int(x_vars[i, j].varValue)
        servers=np.array([int(s.varValue) for s in s_vars.values()])
        print(requests,servers)
        if opt_model.sol_status != 1:
            return np.zeros(n_regions), requests, -10000

        return (
            servers,
            requests,
            objective.value(),
        )

class MilpScheduler:
    def compute_carbon_intensities(server_manager, hour):
        carbon_intensities = [region.carbon_intensity[hour] for region in server_manager.regions]
        return carbon_intensities
    
    def compute_latencies(server_manager, request_batches):
        latencies = np.array(
            [[region.latency(batch.region) for region in server_manager.regions] for batch in request_batches]
        )
        print("compute_args: Latencies:\n",latencies)
        if np.isnan(latencies).any():
            latencies[np.isnan(latencies)] = 10**6
            logging.warning(f"Detected NaN value in latency adjacency matrix. Converted to 10^6 as penalty.")
        return latencies

    def compute_capacities(server_manager):
        capacities = [Config.SERVER_CAPACITY] * len(server_manager.regions)
        print("compute_args: capacities:\n",capacities)
        return capacities

    def compute_request_rates(request_batches):
        # Hourly request rate taken from the batches
        request_rates = np.array([batch.load for batch in request_batches], dtype=np.int64)
        print("compute_args: request_rates:\n",request_rates)
        return request_rates

    def validate_objective_value(obj_val, hour, carbon_intensities, latencies, capacities, request_rates):
        if obj_val < 0:
            logging.warning(
                f"\nCould not place servers! t={hour}\n"
                f"reqs: {request_rates}\n"
                f"caps: {capacities}\n"
                f"acc_reqs={sum(request_rates)}\n"
                f"acc_cap={sum(capacities)}\n"
                f"latency={latencies}\n"
                f"carbon_intenisties={carbon_intensities}\n"
            )
            raise Exception("Infeasible problem, look above for more info")

    @classmethod
    def schedule_servers(cls,
        request_batches,
        server_manager,
        hour
    ):
        """
        Wrapper around the CAP
        """
        print("**************CAP RUNNING**************")
        carbon_intensities = cls.compute_carbon_intensities(server_manager, hour)
        latencies = cls.compute_latencies(server_manager, request_batches)
        capacities = cls.compute_capacities(server_manager)
        request_rates = cls.compute_request_rates(request_batches)
        if Config.SCHEDULER == "carbon":
            servers, requests, obj_val = Carbon.schedule_servers(carbon_intensities, latencies, capacities,request_rates)
        elif Config.SCHEDULER == "latency":
            servers, requests, obj_val = Latency.schedule_servers(carbon_intensities, latencies, capacities,request_rates)
        else:
            raise Exception("Invalid scheduler")

        print("CAP output: Requests redirected:\n ",requests)
        print("CAP output: Servers:\n ",servers)
        cls.validate_objective_value(obj_val, hour, carbon_intensities, latencies, capacities, request_rates)
        # If we never plan to schedule at a region, we set the servers in that region to 0.
        mask = np.sum(requests, axis=0) == 0
        servers[mask] = 0

        return servers,requests,carbon_intensities,latencies

    def schedule_requests(
        conf,
        request_batches,
        server_manager,
        t,
        request_update_interval,
        max_latency,
    ):
        """
        Wrapper around the CAS
        """
        print("**************CAS RUNNING**************")
        carbon_intensities = cls.compute_carbon_intensities(server_manager, hour)
        latencies = cls.compute_latencies(server_manager, request_batches)
        capacities = cls.compute_capacities(server_manager)
        request_rates = cls.compute_request_rates(request_batches)
        if conf.scheduler == "carbon":
            requests, obj_val = Carbon.schedule_requests(*schedule_args)
        elif conf.scheduler == "latency":
            requests, obj_val = Latency.schedule_requests(*schedule_args)
        else:
            raise Exception("Invalid scheduler")
        print("CAS output: Requests redirected:\n ",requests)
        validate_objective_value(obj_val, t, *args)

        carbon_intensities, _, latencies, *_ = args
        print("Cas output: Latencies: ", latencies)
        return latencies, carbon_intensities, requests
