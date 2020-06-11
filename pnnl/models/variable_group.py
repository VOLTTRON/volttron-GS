import itertools
import numpy as np
import pandas
import pulp

__all__ = ['VariableGroup', 'RANGE']

# variable to indicate that we want all variables that match a pattern
# one item in the tuple key can be RANGE
RANGE = -1



def binary_var(name):
    return pulp.LpVariable(name, 0, 1, pulp.LpInteger)


def constant(x):
    def _constant(*args, **kwargs):
        return x

    return _constant


class VariableGroup(object):
    def __init__(self, name, indexes=(), is_binary_var=False, lower_bound_func=None, upper_bound_func=None,
                 base_name=None):
        self.variables = {}

        name_base = name
        for _ in range(len(indexes)):
            name_base += "_{}"

        for index in itertools.product(*indexes):
            var_name = name_base.format(*index)

            if is_binary_var:
                var = binary_var(var_name)
            else:

                # find upper and lower bounds for the variable, if available
                if lower_bound_func is not None:
                    lower_bound = lower_bound_func(index)
                else:
                    lower_bound = None

                if upper_bound_func is not None:
                    upper_bound = upper_bound_func(index)
                else:
                    upper_bound = None

                # # the lower bound should always be set if the upper bound is set
                # if lower_bound is None and upper_bound is not None:
                #     raise RuntimeError("Lower bound should not be unset while upper bound is set")

                # create the lp variable
                if lower_bound is not None and upper_bound is not None:
                    #print("name: {}, lower_bound: {}, upper_bound: {}".format(var_name, lower_bound, upper_bound))
                    var = pulp.LpVariable(var_name, lowBound=lower_bound, upBound=upper_bound)
                elif lower_bound is not None and upper_bound is None:
                    #print("name: {}, lower_bound: {}, ".format(var_name, lower_bound))
                    var = pulp.LpVariable(var_name, lowBound=lower_bound)
                elif lower_bound is None and upper_bound is not None:
                    #print("name: {}, upper_bound: {}, ".format(var_name, upper_bound))
                    var = pulp.LpVariable(var_name, lowBound=None, upBound=upper_bound)
                else:
                    #print("name: {} ".format(var_name))
                    var = pulp.LpVariable(var_name)

                # if upper_bound is not None:
                #     print("name: {}, lower_bound: {}, upper_bound: {}".format(var_name, lower_bound, upper_bound))
                #     var = pulp.LpVariable(var_name, lower_bound, upper_bound)
                # elif lower_bound is not None:
                #     print("name: {}, lower_bound: {}, ".format(var_name, lower_bound))
                #     var = pulp.LpVariable(var_name, lower_bound)
                # else:
                #     print("name: {} ".format(var_name))
                #     var = pulp.LpVariable(var_name)

            self.variables[index] = var

    def match(self, key):
        def predicate(xs, ys):
            z = 0
            for x, y in zip(xs, ys):
                if x - y == 0:
                    z += 1
            return z == len(key) - 1

        position = key.index(RANGE)
        keys = list(self.variables.keys())
        keys = [k for k in keys if predicate(k, key)]
        keys.sort(key=lambda k: k[position])

        return [self.variables[k] for k in keys]

    def __getitem__(self, key):
        if type(key) != tuple:
            key = (key,)

        n_ones = 0
        for i, x in enumerate(key):
            if x == RANGE:
                n_ones += 1

        if n_ones == 0:
            return self.variables[key]
        elif n_ones == 1:
            return self.match(key)
        else:
            raise ValueError("Can only get RANGE for one index.")
