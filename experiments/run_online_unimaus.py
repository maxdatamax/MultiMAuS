"""
This module provides an online API for the Unimaus Simulator. This can be useful in cases where
we want to have other code interacting with the simulator online, and don't necessarily need to
store the generated data in a file.

For a simple example of usage, see __main__ code at the bottom of this module.

@author Dennis Soemers (only the online API: Luisa Zintgraf developed the original simulator)
"""

from data.features.aggregate_features import AggregateFeatures
from data.features.apate_graph_features import ApateGraphFeatures
from simulator import parameters
from simulator.transactions_unimaus import UniMausTransactionModel
from simulator.customer_unimaus import GenuineCustomer, FraudulentCustomer


class OnlineUnimaus:

    def __init__(self, params=None):
        """
        Creates an object that can be used to run the simulator online / interactively. This means
        that we can have it generate a bit of data, do something with the data, generate a bit more
        data, do something again, etc. (as opposed to, generating one large batch of data, storing it
        in a file, and then using it in a different program).

        :param params:
            Parameters passed on to the UniMausTransactionModel. Will use the default parameters if None
        """
        if params is None:
            params = parameters.get_default_parameters()

        self.model = UniMausTransactionModel(params, GenuineCustomer, FraudulentCustomer)
        self.aggregate_feature_constructor = None
        self.apate_graph_feature_constructor = None

    def clear_log(self):
        """
        Clears all transactions generated so far from memory
        """
        agent_vars = self.model.log_collector.agent_vars
        for reporter_name in agent_vars:
            for agent_records in agent_vars[reporter_name]:
                agent_records.clear()

    def get_log(self, clear_after=True):
        """
        Returns a log (in the form of a pandas dataframe) of the transactions generated so far.

        :param clear_after:
            If True, will clear the transactions from memory. This means that subsequent calls to get_log()
            will no longer include the transactions that have already been returned in a previous call.
        :return:
            The logged transactions
        """
        log = self.model.log_collector.get_agent_vars_dataframe()
        log.index = log.index.droplevel(1)

        if clear_after:
            self.clear_log()

        return log

    def step_simulator(self, num_steps=1):
        """
        Runs num_steps steps of the simulator (simulates num_steps hours of transactions)

        :param num_steps:
            The number of steps to run. 1 by default.
        :return:
            True if we successfully simulated a step, false otherwise
        """
        for step in range(num_steps):
            if self.model.terminated:
                print("WARNING: cannot step simulator because model is already terminated. ",
                      "Specify a later end_date in params to allow for a longer simulation.")
                return False

            self.model.step()
            return True

    def prepare_feature_constructors(self, data):
        """
        Prepares feature constructors (objects which can compute new features for us) using
        a given set of ''training data''. The training data passed into this function should
        NOT be re-used when training predictive models using the new features, because the new
        features will likely be unrealistically accurate on this data (and therefore models
        trained on this data would learn to rely on the new features too much)

        :param data:
            Data used to ''learn'' features
        """
        self.aggregate_feature_constructor = AggregateFeatures(data)
        self.apate_graph_feature_constructor = ApateGraphFeatures(data)

    def process_data(self, data):
        """
        Processes the given data, so that it will be ready for use in Machine Learning models. New features
        are added by the feature constructors, features which are no longer necessary afterwards are removed,
        and the Target feature is moved to the back of the dataframe

        NOTE: processing is done in-place

        :param data:
            Data to process
        :return:
            Processed dataframe
        """
        self.apate_graph_feature_constructor.add_graph_features(data)
        self.aggregate_feature_constructor.add_aggregate_features(data)

        # remove non-numeric columns / columns we don't need after adding features
        data.drop(["Global_Date", "Local_Date", "CardID", "MerchantID", "Currency", "Country"], inplace=True, axis=1)

        # move Target column to the end
        data = data[[col for col in data if col != "Target"] + ["Target"]]

        return data

    def update_feature_constructors_unlabeled(self, data):
        """
        Performs an update of existing feature constructors, treating the given new data
        as being unlabeled.

        :param data:
            (unlabeled) new data (should NOT have been passed into prepare_feature_constructors() previously)
        """
        self.aggregate_feature_constructor.update_unlabeled(data)

class DataLogWrapper:

    def __init__(self, dataframe):
        """
        Constructs a wrapper for a data log (in a dataframe). Provides some useful functions to make
        it easier to access this data from Java through jpy. This class is probably not very useful in
        pure Python.

        :param dataframe:
            The dataframe to wrap in an object
        """
        self.dataframe = dataframe

    def get_column_names(self):
        """
        Returns a list of column names

        :return:
            List of column names
        """
        return self.dataframe.columns

    def get_data_list(self):
        """
        Returns a flat list representation of the dataframe

        :return:
        """
        return [item for sublist in self.dataframe.as_matrix().tolist() for item in sublist]

    def get_num_cols(self):
        """
        Returns the number of columns in the dataframe

        :return:
            The number of columns in the dataframe
        """
        return self.dataframe.shape[1]

    def get_num_rows(self):
        """
        Returns the number of rows in the dataframe

        :return:
            The number of rows in the dataframe
        """
        return self.dataframe.shape[0]

if __name__ == '__main__':
    # construct our online simulator
    simulator = OnlineUnimaus()

    # change this value to change how often we print logged transactions.
    # with n_steps = 1, we print after every hour of transactions.
    # with n_steps = 2 for example, we would only print every 2 steps
    n_steps = 1

    # if this is set to False, our simulator will not clear logged transactions after printing them.
    # This would mean that subsequent print statements would also re-print transactions that we've already seen earlier
    clear_logs_after_print = True

    # keep running until we fail (which will be after 1 year due to end_date in default parameters)
    while simulator.step_simulator(n_steps):
        # print the transactions generated by the last step
        print(simulator.get_log(clear_logs_after_print))