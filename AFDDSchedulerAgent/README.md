# AFDDSchedulerAgents Agent
There may be a secondary AFDD
(analyze hours of operation for RTUs with inherent heating capability) or simply forego using discharge
temperature as a proxy for proof of fan operations. Optimal Start is not accounted for 
(in determination of an earlier start time than the schedule) nor is the night setback
minimum and maximum space temperature configuration that will cause the RTU to operate during
unoccupied hours to maintain the building space temperatures at the specified minimum and maximum temperatures.

## AFDDSchedulerAgent Agent Configuration

The json format of the config files are specified below. 

*  Agent config file:

```
{
    "analysis_name": "analysis",
    "campus": "PNNL",
    "building": "BUILDING1",
    "maximum_hour_threshold" :5.0,
    "excess_operation": false,
    "interval": 60,
    "timezone": "US/Pacific",
    "simulation": true,
    "year": 2021,
    #"device": {
    #        "AHU1": ["VAV102", "VAV118"],
    #        "AHU3": ["VAV104", "VAV105"]
    #    },
    "device":["AHU1", "AHU3"],
    "schedule" : {
        "weekday": ["6:00","18:00"],
        "weekend_holiday": ["0:00","0:00"]
    },
    "condition_list": {
        "conditions": ["DischargeAirTemperature > 75.0", "SupplyFanStatus"],
        "condition_args": ["SupplyFanStatus", "DischargeAirTemperature"]
    }
}
````

## Install and activate VOLTTRON environment
For installing, starting, and activating the VOLTTRON environment, refer to the following VOLTTRON readthedocs: 
https://volttron.readthedocs.io/en/develop/introduction/platform-install.html

## Installing and Running AFDDSchedulerAgent Agent
Install and start the AFDDSchedulerAgent Agent using the script install-agent.py as describe below:

```
python VOLTTRON_ROOT/scripts/install-agent.py -s <top most folder of the agent> 
                                -c <Agent config file> \
                                -i agent.AFDDSchedulerAgent \
                                -t AFDDSchedulerAgent \
                                --start \
                                --force
```
, where VOLTTRON_ROOT is the root of the source directory of VOLTTRON.

-s : path of top most folder of the ILC agent

-c : path of the agent config file

-i : agent VIP identity

-t : agent tag
 
--start (optional): start after installation

--force (optional): overwrites existing AFDDSchedulerAgents agent with identity "agent.AFDDSchedulerAgent" 


