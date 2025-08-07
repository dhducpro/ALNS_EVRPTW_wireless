from EVRPTW_PR_ALNS.file_reader import get_parameters
from EVRPTW_PR_ALNS.helper_function import Helper
from EVRPTW_PR_ALNS.Initial import Heuristic
from EVRPTW_PR_ALNS._algorithms.CR import CustomerRemoval
from EVRPTW_PR_ALNS._algorithms.CI import CustomerInsertion
from EVRPTW_PR_ALNS._algorithms.SR import StationRemoval
from EVRPTW_PR_ALNS._algorithms.SI import StationInsertion
from random import random, choices
from math import log, exp
from time import time


class ALNS:
    def __init__(self, file: str, wireless_coverage: str = "none"):
        """
        Initialize ALNS with wireless charging support (silent version)
        :param file: instance file path
        :param wireless_coverage: wireless coverage level ("none", "light", "moderate", "high")
        """
        self.parameters = get_parameters(file, wireless_coverage=wireless_coverage)
        self.helper = Helper(self.parameters)
        self.cr = CustomerRemoval(self.parameters)
        self.ci = CustomerInsertion(self.parameters)
        self.sr = StationRemoval(self.parameters)
        self.si = StationInsertion(self.parameters)
        self.initial = Heuristic(self.parameters)
        self.wireless_coverage = wireless_coverage

    def run(
            self, sigma1=30, sigma2=20, sigma3=13, rho=0.45, epsilon=0.9994, mu=0.05, N=25000, Nc=200,
            Ns=1000, NRR=6000, NSR=10, nRR=1250
    ):
        # initiate algorithms, initial solution and helper functions
        helper = Helper(self.parameters)

        # get the initial solution using the heuristic
        initial_solution = self.initial.initial_solution()

        # get the initial temperature
        initial_distance = self.helper.total_distance_list(initial_solution)
        T = -(mu * initial_distance) / log(0.5)

        # create the list and dict of the functions
        normal_cr_function_dict = self.normal_cr_function_dict()
        route_cr_function_dict = self.route_cr_function_dict()
        ci_function_dict = self.ci_function_dict()
        sr_function_dict = self.sr_function_dict()
        si_function_dict = self.si_function_dict()

        normal_cr_list = [key for key, value in normal_cr_function_dict.items()]
        route_cr_list = [key for key, value in route_cr_function_dict.items()]
        ci_list = [key for key, value in ci_function_dict.items()]
        sr_list = [key for key, value in sr_function_dict.items()]
        si_list = [key for key, value in si_function_dict.items()]

        # create the dict to calculate weight, score and times to be called
        score_normal_cr = {}
        score_route_cr = {}
        score_ci = {}
        score_sr = {}
        score_si = {}

        for key in normal_cr_list:
            score_normal_cr[key] = [1, 0, 0]
        for key in route_cr_list:
            score_route_cr[key] = [1, 0, 0]
        for key in ci_list:
            score_ci[key] = [1, 0, 0]
        for key in sr_list:
            score_sr[key] = [1, 0, 0]
        for key in si_list:
            score_si[key] = [1, 0, 0]

        # start the process, first to define some parameters
        best_solution = initial_solution
        prev_solution = initial_solution

        # this is the process of ALNS
        start_time = time()

        for i in range(1, N + 1):
            # Removed print(i) for silent operation
            
            # this is for stations
            if i % NSR == 0:
                # choose the station removal and station insertion
                sr_weights = [value[0] for key, value in score_sr.items()]
                sr_algo = choices(sr_list, weights=sr_weights, k=1)[0]

                si_weights = [value[0] for key, value in score_si.items()]
                si_algo = choices(si_list, weights=si_weights, k=1)[0]

                # update the calling times of the algorithms
                score_sr[sr_algo][2] += 1
                score_si[si_algo][2] += 1

                # destroy and repair
                destroy = sr_function_dict[sr_algo](prev_solution)
                repair = []
                for route in destroy:
                    repair.append(si_function_dict[si_algo](route))

                # test first whether the repair is feasible or not
                if helper.feasible(repair):
                    # the best one has been found, update the current prev and best, and the score
                    if (
                            len(repair) < len(best_solution) or (
                            len(repair) == len(best_solution) and helper.total_distance_list(
                        repair) < helper.total_distance_list(best_solution))
                    ):
                        prev_solution = repair
                        best_solution = repair
                        score_sr[sr_algo][1] += sigma1
                        score_si[si_algo][1] += sigma1

                    # if this one is better than previous but not the best
                    elif (
                            len(repair) == len(prev_solution) and helper.total_distance_list(
                        repair) < helper.total_distance_list(prev_solution)
                    ):
                        prev_solution = repair
                        score_sr[sr_algo][1] += sigma2
                        score_si[si_algo][1] += sigma2

                    elif (
                            len(repair) == len(prev_solution) and helper.total_distance_list(
                        repair) > helper.total_distance_list(prev_solution)
                    ):
                        prob = exp(-(helper.total_distance_list(repair) - helper.total_distance_list(prev_solution))/T)
                        # accept the solution and update the score
                        if random() <= prob:
                            prev_solution = repair
                            score_sr[sr_algo][1] += sigma3
                            score_si[si_algo][1] += sigma3

            elif i % NRR == 0:
                # this is for route removal
                for _ in range(nRR):
                    route_cr_weights = [value[0] for key, value in score_route_cr.items()]
                    route_cr_algo = choices(route_cr_list, weights=route_cr_weights, k=1)[0]

                    ci_weights = [value[0] for key, value in score_ci.items()]
                    ci_algo = choices(ci_list, weights=ci_weights, k=1)[0]

                    # update the calling times of the algorithms
                    score_route_cr[route_cr_algo][2] += 1
                    score_ci[ci_algo][2] += 1

                    # destroy and repair
                    destroy = route_cr_function_dict[route_cr_algo](prev_solution)
                    repair = ci_function_dict[ci_algo](destroy, self.cr.removal)

                    # test first whether the repair is feasible or not
                    if helper.feasible(repair):
                        # the best one has been found, update the current prev and best, and the score
                        if (
                                len(repair) < len(best_solution) or (
                                len(repair) == len(best_solution) and helper.total_distance_list(
                            repair) < helper.total_distance_list(best_solution))
                        ):
                            prev_solution = repair
                            best_solution = repair
                            score_route_cr[route_cr_algo][1] += sigma1
                            score_ci[ci_algo][1] += sigma1

                        # if this one is better than previous but not the best
                        elif (
                                len(repair) == len(prev_solution) and helper.total_distance_list(
                            repair) < helper.total_distance_list(prev_solution)
                        ):
                            prev_solution = repair
                            score_route_cr[route_cr_algo][1] += sigma2
                            score_ci[ci_algo][1] += sigma2

                        elif (
                                len(repair) == len(prev_solution) and helper.total_distance_list(
                            repair) > helper.total_distance_list(prev_solution)
                        ):
                            prob = exp(
                                -(helper.total_distance_list(repair) - helper.total_distance_list(prev_solution)) / T)
                            # accept the solution and update the score
                            if random() <= prob:
                                prev_solution = repair
                                score_route_cr[route_cr_algo][1] += sigma3
                                score_ci[ci_algo][1] += sigma3

            else:
                # this is for the customer removal and insertion
                # choose the station removal and station insertion
                normal_cr_weights = [value[0] for key, value in score_normal_cr.items()]
                normal_cr_algo = choices(normal_cr_list, weights=normal_cr_weights, k=1)[0]

                ci_weights = [value[0] for key, value in score_ci.items()]
                ci_algo = choices(ci_list, weights=ci_weights, k=1)[0]

                # update the calling times of the algorithms
                score_normal_cr[normal_cr_algo][2] += 1
                score_ci[ci_algo][2] += 1

                # destroy and repair
                destroy = normal_cr_function_dict[normal_cr_algo](prev_solution)
                repair = ci_function_dict[ci_algo](destroy, self.cr.removal)

                # test first whether the repair is feasible or not
                if helper.feasible(repair):
                    # the best one has been found, update the current prev and best, and the score
                    if (
                            len(repair) < len(best_solution) or (
                            len(repair) == len(best_solution) and helper.total_distance_list(
                        repair) < helper.total_distance_list(best_solution))
                    ):
                        prev_solution = repair
                        best_solution = repair
                        score_normal_cr[normal_cr_algo][1] += sigma1
                        score_ci[ci_algo][1] += sigma1

                    # if this one is better than previous but not the best
                    elif (
                            len(repair) == len(prev_solution) and helper.total_distance_list(
                        repair) < helper.total_distance_list(prev_solution)
                    ):
                        prev_solution = repair
                        score_normal_cr[normal_cr_algo][1] += sigma2
                        score_ci[ci_algo][1] += sigma2

                    elif (
                            len(repair) == len(prev_solution) and helper.total_distance_list(
                        repair) > helper.total_distance_list(prev_solution)
                    ):
                        prob = exp(
                            -(helper.total_distance_list(repair) - helper.total_distance_list(prev_solution)) / T)
                        # accept the solution and update the score
                        if random() <= prob:
                            prev_solution = repair
                            score_normal_cr[normal_cr_algo][1] += sigma3
                            score_ci[ci_algo][1] += sigma3

            # end the removal and insertion operation, try to update the weights
            if i % Nc == 0:
                # update the weights of the customers
                for key, value in score_normal_cr.items():
                    if value[2] != 0:
                        score_normal_cr[key][0] = value[0] * (1 - rho) + rho * value[1] / value[2]

                for key, value in score_normal_cr.items():
                    score_normal_cr[key][1] = 0
                    score_normal_cr[key][2] = 0

                for key, value in score_ci.items():
                    if value[2] != 0:
                        score_ci[key][0] = value[0] * (1 - rho) + rho * value[1] / value[2]

                for key, value in score_ci.items():
                    score_ci[key][1] = 0
                    score_ci[key][2] = 0

                for key, value in score_route_cr.items():
                    if value[2] != 0:
                        score_route_cr[key][0] = value[0] * (1 - rho) + rho * value[1] / value[2]

                for key, value in score_route_cr.items():
                    score_route_cr[key][1] = 0
                    score_route_cr[key][2] = 0

            if i % Ns == 0:
                # update the weights of the stations
                for key, value in score_sr.items():
                    if value[2] != 0:
                        score_sr[key][0] = value[0] * (1 - rho) + rho * value[1] / value[2]

                for key, value in score_sr.items():
                    score_sr[key][1] = 0
                    score_sr[key][2] = 0

                for key, value in score_si.items():
                    if value[2] != 0:
                        score_si[key][0] = value[0] * (1 - rho) + rho * value[1] / value[2]

                for key, value in score_si.items():
                    score_si[key][1] = 0
                    score_si[key][2] = 0

            T = T * epsilon

            if ["D0", "D0_end"] in best_solution:
                best_solution.remove(["D0", "D0_end"])

            if ["D0", "D0_end"] in prev_solution:
                prev_solution.remove(["D0", "D0_end"])

        end_time = time()
        duration = end_time - start_time

        return helper.total_distance_list(best_solution), len(best_solution), helper.total_distance_list(
            initial_solution), len(initial_solution), duration, best_solution

    def normal_cr_function_dict(self):
        return {"r": self.cr.random_removal,
                "wd": self.cr.worst_distance_removal,
                "wt": self.cr.worst_time_removal,
                "s": self.cr.shaw_removal,
                "sp": self.cr.shaw_removal_prev,
                "sn": self.cr.shaw_removal_next,
                "z": self.cr.zone_removal,
                "zp": self.cr.zone_removal_prev,
                "zn": self.cr.zone_removal_next}

    def route_cr_function_dict(self):
        return {"RRR": self.cr.random_route_removal_RRR}

    def ci_function_dict(self):
        return {"g": self.ci.greedy_customer_insertion,
                "r2": self.ci.regret_customer_insertion_2,
                "r3": self.ci.regret_customer_insertion_3}

    def sr_function_dict(self):
        return {"r": self.sr.random_removal,
                "wd": self.sr.worst_distance_removal,
                "wc": self.sr.worst_charge_removal,
                "f": self.sr.full_removal}


    def si_function_dict(self):
        return {"gsi": self.si.greedy_station_insertion,
                "gsic": self.si.greedy_station_insertion_comparison,
                "bsi": self.si.best_station_insertion}