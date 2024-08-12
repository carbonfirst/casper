# Authors: Basundhara Chakrabarty, Shruti Jasoria

import os
from datetime import datetime, timezone

import pandas as pd
from .config import Config


class Util:
    def save_file(plot):
        """Save the data of a file by name specified of the arguments. Usefull for misc visualisations.


        Args:
            plot: Converts data from the plot object to dataframe
        """
        df = plot.build_df()
        date_created = datetime.now().strftime("%Y-%m-%d")
        if not os.path.exists("saved"):
            os.makedirs("saved")

        fingerprint = [
            "replay_" if Config.SCHEDULER == "replay" else str(Config.SCHEDULER) + "_",
            str(Config.START_DATE) + "_",
            "_timesteps_",
            str(Config.TIMESTEPS),
            "_max_latency_",
            str(Config.MAX_LATENCY),
            "_max_servers_",
            str(Config.MAX_SERVERS)
        ]
        df.to_csv(f"saved/{date_created}_{''.join(fingerprint)}.csv", index=False)


    # def ui(conf, timestep, request_per_region, servers, servers_per_regions_list):
    #     """Interactive UI while running for debugging

    #     Args:
    #         conf: Runtime configurations to retrieve regions
    #         timestep: Timesteps
    #         request_per_region: Dataframe for hourly request rate
    #         servers: List of servers
    #         servers_per_regions_list: List of servers per region
    #     """
    #     region_names = util.get_regions(conf)
    #     print(f"______________________________________ \n TIMESTEP: {timestep}")
    #     print("Requests per region:")
    #     [print(f"{region_names[i]} - {request[0]}") for i, request in enumerate(request_per_region)]
    #     print(" \n SERVERS PER REGION: \n")
    #     [
    #         print(f"{region_names[i]} - {servers_per_region}")
    #         for i, servers_per_region in enumerate(servers_per_regions_list)
    #     ]
    #     print("\n Server objects in ServerManager: ")
    #     print(servers)
    #     print("______________________________________")

    @classmethod
    def required_files(cls):
        region_dir = cls.__region_dir()
        names = [
            "carbon_intensity.csv",
            "latency.csv",
            "request.csv",
            "offset.csv",
        ]
        print("These files must exist:")
        print(region_dir)
        for name in names:
            print(f"\t{name}")


    def __region_dir():
        scheduler_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.abspath(os.path.join(scheduler_dir, "../CAP/dataset"))
        return os.path.join(data_dir, Config.DATASET)

    @classmethod
    def load_file_as_df(cls, file_name):
        try:
            region_dir = cls.__region_dir()
            file_path = os.path.join(region_dir, file_name)
            #print("### File path", file_path)
            return pd.read_csv(file_path)
        except Exception as e:
            print(f"Failed to load file: {file_name}")
            print(e)
            cls.required_files()


    # Calculate the timestamp from conf.start_date and validate whether an entry for the timestamp is present in file_name. If not present, throw an assertion error
    @classmethod
    def validate_date_and_load_file(cls, file_name):
        df_from_file = cls.load_file_as_df(file_name)
        #start_date = datetime.fromisoformat(Config.START_DATE).replace(tzinfo=timezone.utc)
        start_date= datetime.strptime(Config.START_DATE, '%Y-%m-%d')
        start_date=start_date.replace(tzinfo=timezone.utc)
        start_timestamp = int(start_date.timestamp())
        start_index_in_file = df_from_file.index[df_from_file["timestamp"] == start_timestamp]
        assert len(start_index_in_file) > 0, f"Date [{start_date}] does not exist in file: {file_name}"

        start = start_index_in_file[0]
        
        assert start > 0, start
        end = start + Config.TIMESTEPS + 24
        print("Start date provided:{0}, start timestamp:{1}, start index:{2}, end index:{3} file name:{4}".format(Config.START_DATE,start_timestamp,start,end,file_name))
        assert end < len(df_from_file), f"The selected interval overflows in file: {file_name}"

        return df_from_file, start, end

    @classmethod
    def load_carbon_intensity_from_file(cls):
        df, start, end = cls.validate_date_and_load_file(Config.CARBON_INTENSITY_FILENAME)
        return df.iloc[start:end].reset_index(drop=True)

    def shuffle_requests(requests,rotate=1):
        print("Request before shuffling:",requests.head)
        for i in range(rotate):
            columns=[col for col in requests if col!='datetime' and col!='timestamp']
            tmp=requests[columns[len(columns)-1]].copy()
            for i in range(len(columns)-1,0,-1):
                requests[columns[i]]=requests[columns[i-1]]
            requests[columns[0]]=tmp
        print("Request after shuffling by {0} : ",format(rotate),requests.head)
        return requests

    @classmethod
    def load_request_from_file(cls):
        print("Loading requests")
        df, start, end = cls.validate_date_and_load_file(Config.REQUEST_DATA_FILENAME)
        #df=cls.shuffle_requests(df,rotate=0)
        return df.iloc[start:end].reset_index(drop=True)

    @classmethod
    def load_latency_from_file(cls):
        latency_df=cls.load_file_as_df(Config.LATENCY_FILENAME)
        #print("Latency:",latency_df)
        regions=cls.region_names()
        #Renames the rows to map to each region, in the following way: 
        # {0: 'ap-southeast-2', 1: 'eu-central-1', 2: 'eu-west-3', 3: 'us-east-1', 4: 'us-east-2', 5: 'us-west-1'}
        new_rows={idx:region for idx,region in zip(range(len(regions)),regions)}
        latency_df.rename(index=new_rows, inplace=True)
        return latency_df

    @classmethod
    def load_offset_from_file(cls):
        return cls.load_file_as_df(Config.TIME_OFFSET_FILENAME)

    @classmethod
    def region_names(cls):
        """
        The region names are taken from the offset_wiki data file
        """
        df = cls.load_offset_from_file()
        return df.columns
