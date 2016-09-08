"""
This is where the work is done. 
"""

import config
import notify
from log import Log
from messageQueue import Queue

import json
import requests
import time


class Microscaler:
    containers = [
        {
            "id": "/microscaling/analyzer",
            "name": "analyzer-microscaling.marathon.slave.mesos"
        }
    ]

    cool_off_period = 10 # time to wait between scale requests
    last_scale_up_time = time.time()
    last_scale_down_time = time.time()
    scale_factor = 5

    def __init__(self):
        self.log = Log()
        self.msgQueue = Queue(account_name = config.AZURE_STORAGE_ACCOUNT_NAME, account_key=config.AZURE_STORAGE_ACCOUNT_KEY, queue_name=config.AZURE_STORAGE_QUEUE_NAME)

    def scaleUp(self, container):
        self.last_scale_up_time = time.time()
    
        # Get current instance count
        url = "http://leader.mesos:8080/v2/apps" + container["id"]
        resp = requests.get(url)
        app_data = json.loads(resp.text)
        instances = app_data["app"]["instances"]
    
        # Increment count
        length = self.msgQueue.getLength()
        instances = instances + int(length / 10)
    
        # Put new instance count
        url = "http://leader.mesos:8080/v2/apps" + container["id"]
        data_packet = { "instances": instances }
        notify.info("Scale Data Packet = \n" + str(data_packet))
        resp = requests.put(url, data = json.dumps(data_packet))

        msg = "Response to scale up request: " + resp.text
        notify.info(msg)

    def scaleDown(self, container):
        self.last_scale_down_time = time.time()
    
        # Get current instance count
        url = "http://leader.mesos:8080/v2/apps" + container["id"]
        resp = requests.get(url)
        app_data = json.loads(resp.text)
        instances = app_data["app"]["instances"]
    
        # Decrement count
        instances = instances - 1
        if (instances <= 0):
            return
    
        # Put new instance count
        url = "http://leader.mesos:8080/v2/apps" + container["id"]
        data_packet = { "instances": instances }
        notify.info("Scale Data Packet = \n" + str(data_packet))
        resp = requests.put(url, data = json.dumps(data_packet))

        msg = "Response to scale down request: " + resp.text
        notify.info(msg)

    def autoscale(self):
        while True:
            for container in self.containers:
                resp = requests.get("http://" + container["name"] + ":5000")
                scale_health = json.loads(resp.text)
        
                status = scale_health["status"]
                now = time.time()
                if self.last_scale_down_time < self.last_scale_up_time:
                    time_since_last_scale = now - self.last_scale_down_time
                else:
                    time_since_last_scale = now - self.last_scale_up_time
                if time_since_last_scale > self.cool_off_period:
                    if status < 0:
                        time_since_last_scale = now - self.last_scale_down_time
                        status = status - (time_since_last_scale * self.scale_factor)
                    elif status > 0:
                        time_since_last_scale = now - self.last_scale_up_time
                        status = status + (time_since_last_scale * self.scale_factor)

                    msg = "Scale need for analyzer: " + str(status) + "\n (time since last scale = " + str(time_since_last_scale) + ", scale factor = " + str(self.scale_factor) + ", scale health from container = " + str(scale_health["status"]) + ")"
                    notify.info(msg)
            
                if  status >= 100:
                    self.scaleUp(container)
                elif status <= -100:
                    self.scaleDown(container)

            time.sleep(5)

if __name__ == "__main__":
    scaler = Microscaler()
    scaler.autoscale()
        

