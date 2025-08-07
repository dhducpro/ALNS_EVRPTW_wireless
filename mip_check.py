import numpy as np
import random


class MIPCheck:
    def __init__(self, parameters):
        self.parameters = parameters
        self.clients = self.parameters["clients"]
        self.stations = self.parameters["stations"]
        self.all_nodes = self.parameters["all_nodes"]
        self.depot_start = self.parameters["depot_start"]
        self.depot_end = self.parameters["depot_end"]
        self.demand = self.parameters["demand"]
        self.ready_time = self.parameters["ready_time"]
        self.due_date = self.parameters["due_date"]
        self.service_time = self.parameters["service_time"]
        self.arcs = self.parameters["arcs"]
        self.times = self.parameters["normal_times"]
        self.C = self.parameters["C"]
        self.Q = self.parameters["Q"]
        self.g = self.parameters["g"]
        self.h = self.parameters["h"]
        self.v = self.parameters["v"]
        self.std = self.parameters["std"]
        self.mean = self.parameters["mean"]
        
        # Wireless charging integration (silent)
        if "net_energy_consumption" in self.parameters:
            self.net_energy_consumption = self.parameters["net_energy_consumption"]
        else:
            # Fallback to original energy calculation
            self.net_energy_consumption = {}
            for (i, j), distance in self.arcs.items():
                self.net_energy_consumption[(i, j)] = self.h * distance

    def update_times(self, p, n):
        """Update travel times with stochastic variation"""
        new_times = self.parameters["times"].copy()
        for i in self.all_nodes:
            for j in self.all_nodes:
                if i != j:
                    if random.random() < p:
                        stochastic = np.random.normal(0, n*self.std, 1)[0]
                        if new_times[i,j] + stochastic > 0:
                            new_times[i,j] = new_times[i,j] + stochastic
        self.times = new_times

    def get_energy_consumption(self, node_i, node_j):
        """Get energy consumption for arc (i,j) - uses wireless charging if available"""
        return self.net_energy_consumption[node_i, node_j]

    def time_energy(self, route) -> bool:
        """
        Fast feasibility check for both time and energy constraints
        :param route: the list of nodes, one route
        :return: true if the route is feasible, false otherwise
        """
        if len(route) < 2:
            return True
        
        try:
            # Initialize at depot
            current_time = self.ready_time[route[0]]
            current_energy = self.Q
            
            for i in range(len(route) - 1):
                current_node = route[i]
                next_node = route[i + 1]
                
                # === TIME CONSTRAINTS ===
                travel_time = self.times[current_node, next_node]
                
                # Add service time for current node (not for stations during charging)
                if current_node in self.stations:
                    # At station: add recharging time
                    # For simplicity, assume full recharge (can be modified for partial)
                    recharge_amount = self.Q - current_energy
                    if recharge_amount > 0:
                        recharge_time = recharge_amount / self.g
                        current_time += recharge_time
                    current_energy = self.Q  # Full recharge
                else:
                    # At customer or depot: add service time
                    current_time += self.service_time[current_node]
                
                # Travel to next node
                current_time += travel_time
                
                # Check time window feasibility
                if current_time > self.due_date[next_node]:
                    return False
                
                # Adjust for early arrival
                current_time = max(current_time, self.ready_time[next_node])
                
                # === ENERGY CONSTRAINTS ===
                energy_consumption = self.get_energy_consumption(current_node, next_node)
                current_energy -= energy_consumption
                
                # Check if we have enough energy
                if current_energy < 0:
                    return False
            
            return True
            
        except (KeyError, ZeroDivisionError, ValueError):
            # Handle any errors gracefully
            return False

    def time(self, route) -> bool:
        """
        Fast feasibility check for time constraints only
        :param route: list of nodes which is a route
        :return: true if time constraints are satisfied
        """
        if len(route) < 2:
            return True
        
        try:
            current_time = self.ready_time[route[0]]
            
            for i in range(len(route) - 1):
                current_node = route[i]
                next_node = route[i + 1]
                
                # Add service time (stations don't have service time in time-only check)
                if current_node not in self.stations:
                    current_time += self.service_time[current_node]
                
                # Travel time
                travel_time = self.times[current_node, next_node]
                current_time += travel_time
                
                # Check time window
                if current_time > self.due_date[next_node]:
                    return False
                
                # Adjust for early arrival
                current_time = max(current_time, self.ready_time[next_node])
            
            return True
            
        except (KeyError, ValueError):
            return False

    def energy(self, route) -> bool:
        """
        Fast feasibility check for energy constraints only
        :param route: list of nodes
        :return: true if energy constraints are satisfied
        """
        if len(route) < 2:
            return True
        
        try:
            current_energy = self.Q
            
            for i in range(len(route) - 1):
                current_node = route[i]
                next_node = route[i + 1]
                
                # Recharge at stations
                if current_node in self.stations:
                    current_energy = self.Q  # Full recharge
                
                # Consume energy for travel
                energy_consumption = self.get_energy_consumption(current_node, next_node)
                current_energy -= energy_consumption
                
                # Check feasibility
                if current_energy < 0:
                    return False
            
            return True
            
        except (KeyError, ValueError):
            return False

    def time_extractor(self, route):
        """
        Extract arrival times for each node in the route
        :param route: list of nodes
        :return: list of arrival times
        """
        if len(route) < 2:
            return [self.ready_time[route[0]]] if route else []
        
        try:
            times = []
            current_time = self.ready_time[route[0]]
            times.append(current_time)
            
            for i in range(len(route) - 1):
                current_node = route[i]
                next_node = route[i + 1]
                
                # Add service/recharge time at current node
                if current_node in self.stations:
                    # Estimate recharge time (assuming some recharge needed)
                    recharge_time = (self.Q * 0.5) / self.g  # Rough estimate
                    current_time += recharge_time
                else:
                    current_time += self.service_time[current_node]
                
                # Travel to next node
                travel_time = self.times[current_node, next_node]
                current_time += travel_time
                
                # Adjust for time window
                current_time = max(current_time, self.ready_time[next_node])
                times.append(current_time)
            
            return times
            
        except (KeyError, ValueError):
            raise Exception("This route is not feasible")

    def energy_extractor(self, route):
        """
        Extract arrival energy levels for each node in the route
        :param route: list of nodes
        :return: list of arrival energy levels
        """
        if len(route) < 2:
            return [self.Q] if route else []
        
        try:
            energies = []
            current_energy = self.Q
            energies.append(current_energy)
            
            for i in range(len(route) - 1):
                current_node = route[i]
                next_node = route[i + 1]
                
                # Recharge at stations (before leaving)
                if current_node in self.stations:
                    current_energy = self.Q
                
                # Consume energy for travel
                energy_consumption = self.get_energy_consumption(current_node, next_node)
                current_energy -= energy_consumption
                
                energies.append(current_energy)
            
            return energies
            
        except (KeyError, ValueError):
            raise Exception("This route is not feasible")

    def energy_extractor_departure(self, route):
        """
        Extract departure energy levels for each node in the route
        :param route: list of nodes
        :return: list of departure energy levels
        """
        if len(route) < 2:
            return [self.Q] if route else []
        
        try:
            departure_energies = []
            current_energy = self.Q
            
            for i in range(len(route)):
                current_node = route[i]
                
                # Recharge at stations
                if current_node in self.stations:
                    current_energy = self.Q  # Full recharge
                
                departure_energies.append(current_energy)
                
                # If not the last node, consume energy for next travel
                if i < len(route) - 1:
                    next_node = route[i + 1]
                    energy_consumption = self.get_energy_consumption(current_node, next_node)
                    current_energy -= energy_consumption
            
            return departure_energies
            
        except (KeyError, ValueError):
            raise Exception("This route is not feasible")