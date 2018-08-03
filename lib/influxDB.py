#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This module implements the basic functions needed
#   to interface to InfluxDB
#
# Author:
#   Thomas Hein
#

import socket
from influxdb import InfluxDBClient
from glideinwms.lib import logSupport


class influxDB:
    def __init__(self):
        '''
        This is a hard coded example of how to connect muitiple databases

        self.db_credentials = [
            ['localhost', 8086, 'root', 'root', 'frontend_stats'],
            ['fermicloud532.fnal.gov', 8086, 'frontend93824', 'd43h7487y4328', 'gwms_stats']]
        '''
        self.db_credentials = []

        self.databases = []

        # Connect to databases
        for currDB in self.db_credentials:
            try:
                # Connect to the database with the credentials
                self.databases.append(InfluxDBClient(currDB[0], currDB[1], currDB[2], currDB[3], currDB[4]))

                # Create the database if it has not yet been created
                self.databases[-1].create_database(currDB[4])
            except Exception, e:
                # Errror connecting to currDB
                logSupport.log.warning("InfluxDB: Cannot connect to '%s' database. Error: %s" % (currDB[4], str(e)))

        # Host Info
        self.hostname = str(socket.gethostname())


    def SubmitData(self, name, json_data):
        # Loop over each database
        for currDBClient in self.databases:
            # Takes the prepared data and submits to the databases
            try:
                currDBClient.write_points(json_data)
            except Exception, e:
                # Error when submitting data
                logSupport.log.warning("InfluxDB: Cannot submit dataset for %s. Error: %s" % (name, str(e)))


    def Frontend_groupStats(self, data):
        json_body = [];

        # States Data for Frontend
        # data['states']
        name = "Frontend.states."

        for currState, value in data['states'].iteritems():
            for currAttribute, value2 in value.iteritems():
                if (isinstance(value2, dict)):
                    for subElemKey, subElemValue in value2.iteritems():
                        if (isinstance(subElemValue, dict)):
                            print(subElemKey)
                            value2[subElemKey] = str(subElemValue)
                    if value2: # Check for empty dictionaries
                        json_body.append({"measurement": name+currAttribute, "tags": {"State": currState, "Type": "Frontend", "Host": self.hostname}, "fields": value2})
                else:
                    if value2: # Check for empty dictionaries
                        json_body.append({"measurement": name+"Status", "tags": {"State": currState, "Type": "Frontend", "Host": self.hostname}, "fields": {currAttribute: value2}})


        # States Data for Factories
        # data['factories']
        name = "Frontend.states."

        for currHost, value in data['factories'].iteritems():
            for currAttribute, value2 in value.iteritems():
                if (isinstance(value2, dict)):
                    for subElemKey, subElemValue in value2.iteritems():
                        if (isinstance(subElemValue, dict)):
                            print(subElemKey)
                            value2[subElemKey] = str(subElemValue)
                    if value2: # Check for empty dictionaries
                        json_body.append({"measurement": name+currAttribute, "tags": {"Type": "Factory", "FactoryHost": currHost, "Host": self.hostname}, "fields": value2})
                else:
                    if value2: # Check for empty dictionaries
                        json_body.append({"measurement": name+"Status", "tags": {"Type": "Factory", "FactoryHost": currHost, "Host": self.hostname}, "fields": {currAttribute: value2}})

        # Totals Data for Frontend
        # data['totals']
        name = "Frontend.Totals"

        for type, value in data['totals'].iteritems():
            if (isinstance(value, dict)):
                if value:
                    json_body.append({"measurement": name, "tags": {"Type": type, "Host": self.hostname}, "fields": value})

        # Done collecting data, now submit
        self.SubmitData("Frontend_groupStats", json_body)


    def Factory_condorQStats(self, data):
        json_body = [];

        # condorQStats for Factory
        name = "Factory.condorQStats"
        
        if data: # Check for empty dictionary
            json_body.append({"measurement": name, "tags": {"Type": "Factory", "Host": self.hostname}, "fields": data})

        # Done collecting data, now submit
        self.SubmitData("Factory_condorQStats", json_body)


    def Factory_condorLogSummary(self, data):
        json_body = [];

        # condorQStats for Factory
        name = "Factory.condorLogSummary."
        
        if data[0]: # Check for empty dictionary
            json_body.append({"measurement": name+"Log_Counts", "tags": {"Type": "Factory", "Host": self.hostname}, "fields": data[0]})

        if data[1]: # Check for empty dictionary
            json_body.append({"measurement": name+"Log_Completed", "tags": {"Type": "Factory", "Host": self.hostname}, "fields": data[1]})

        if data[2]: # Check for empty dictionary
            json_body.append({"measurement": name+"Log_Completed_Stats", "tags": {"Type": "Factory", "Host": self.hostname}, "fields": data[2]})

        if data[3]: # Check for empty dictionary
            json_body.append({"measurement": name+"Log_Completed_WasteTime", "tags": {"Type": "Factory", "Host": self.hostname}, "fields": data[3]})

        # Done collecting data, now submit
        self.SubmitData("Factory_condorQStats", json_body)
