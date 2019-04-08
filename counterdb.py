#!/usr/bin/env python3
"""
An MQTT service note which provides a persistant counter source.
"""

import sys
import os
import re
import time
import threading
import json
import sqlite3
import paho.mqtt.client as mqtt
import Flask

def topicJoin(*args):
    return "/".join(args)

def stripSQLWhitespace(text):
    "Attempt to strip irrelivant differences between SQL statements"
    return re.sub(re.compile('\s+'), '', text) # This needs to be smarter, it strips too much

class CounterDB:
    "Persistant database interface for counter service."

    SCHEMA = {
        "topics":  "CREATE TABLE topics (id INTEGER PRIMARY KEY, topic TEXT UNIQUE NOT NULL)",
        "events":  "CREATE TABLE events (id INTEGER PRIMARY KEY, topic INTEGER, time REAL, count REAL, payload TEXT, FOREIGN KEY(topic) REFERENCES topics(id))",
        "publish": "CREATE TABLE publish (id INTEGER PRIMARY KEY, queryTopic INTEGER, schedule INTEGER, publishTopic TEXT UNIQUE NOT NULL, query TEXT NOT NULL, FOREIGN KEY(queryTopic) REFERENCES topics(id))",
    }
    
    # Schedule enumeration used in publish table, do not modify or the schema will break
    NO_SCHEDULE = 0
    MINUTELY = 1
    HOURLY = 2
    DAILY = 3
    WEEKLY = 4
    MONTHLY = 5
    

    def setupDatabase(self):
        "Checks the database tables and schema and updates if nessisary"
        cursor = self.db.cursor()
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for name, sql in tables:
            if name not in self.SCHEMA:
                sys.exit("Database file has unexpected table, {}, aborting".format(t))
            elif stripSQLWhitespace(sql) != stripSQLWhitespace(self.SCHEMA[name]):
                sys.exit("Database table {} has differining schema{linesep}\tFile:     {}{linesep}\tExpected: {}{linesep}Aborting.".format(name, sql, self.SCHEMA[name], linesep=os.linesep))
        existingTableNames = [name for name, sql in tables]
        for table in ("topics", "events", "publish"): # Explicit to get the right order to happen
            sql = self.SCHEMA[table]
            if not table in existingTableNames:
                cursor.execute(sql)
                print("Created table", table)

    def __init__(self, database):
        "Initalizes the persistant database connection, initalizing the database if nessisary"
        self.db = sqlite3.connect(database)
        self.setupDatabase()

    def __del__(self):
        self.db.close()

    def query(self, query, cursor=None):
        "Run a query on the database"
        if cursor is None:
            cursor = self.db.cursor()
        cursor.execute(query)
        return cursor.fetchall()

    @staticmethod
    def getTopicID(self, cursor, topic):
        "Returns the ID of a given topic name"
        cursor.execute("SELECT id from topics WHERE name='{}'".format(topic))
        rslt = cursor.fetchall()[0]
        if len(result) != 1:
            raise ValueError("Couldn't retrieve topic ID for \"{}\": {}".format(topic, repr(result)))
        else:
            return rslt[0]

    @property
    def topics(self):
        "Count topics to subscribe do"
        return self.query("SELECT topic FROM topics")

    def createTopic(self, topic):
        "Create a new count topic."
        return self.query("INSERT INTO topics (topic) VALUES('{}')".format(topic))

    def update(self, topic, increment, payload=None):
        "Logs an event for the specified topic. Returns the toptic id"
        cursor = self.db.cursor()
        tid = self.getTopicID(cursor, topic)
        if payload is not None and type(payload) != str:
            payload = json.dumps(payload)
        cursor.execute("INSERT INTO events (topic, time, count, payload) VALUES({topic}, {time}, {count}, '{payload}')".format(topic=tid, time=time.time(), count=increment, payload=payload))
        return tid;
    
    def createPublication(self, queryTopic, publishTopic, query, schedule=NO_SCHEDULE):
        "Adds an entry to the scheduled topics"
        cursor = self.db.cursor()
        tid = self.getTopicID(cursor, queryTopic)
        return self.query("INSERT INTO publish (queryTopic, schedule, publishTopic, query) VALUES({querryTopic}, {schedule}, {publishTopic}, {query})".format(querryTopic=tid, publishTopic=publishTopic, query=query, schedule=schedule), cursor)
        
    def deletePublication(self, id):
        "Removes a publication from the list"
        return self.query("DELETE FROM publish WHERE id={:d}".format(id))

    def getTopicPublications(self, topic):
        "Returns the publications which querry the given topic."
        cursor = self.db.cursor()
        if type(topic) is not int:
            topic = self.getTopicID(topic)
        return self.query("SELECT publishTopic, query FROM publish WHERE queryTopic={:d}".format(topic), cursor)
        
    def getSchedulePublications(self, schedule):
        "Returns the publications which have the given schedule"
        return self.query("SELECT queryTopic, publishTopic, query FROM publish WHERE schedule={:d}".format(schedule))
        

class CounterService:
    "MQTT sercvice which listens for increment messages and publishes counts"

    def vprint(self, level, text, out=sys.stdout):
        if level > self.verbose:
            out.write(text)
            out.write(os.linesep)
            
    def eprint(self, text, out=sys.stderr):
        out.write(text)
        out.write(os.linesep)
        out.flush()

    def publishTopicUpdates(self, topic):
        "Publishes all updates for a given topic"
        for publishTopic, query in self.db.getTopicPublications(t):
            self.vprint(2, "Publishing update for \"{}\"".format(publishTopic))
            self.vprint(3, "\tquery = {}".format(query))
            result = json.dumps(self.db.query(query))
            self.vprint(3, "\tresult = {}".format(result))
            client.publish(publishTopic, result, qos=1, retain=True)

    def on_connect(self, client, userdata, flags, rc):
        "MQTT client callback on connection to the broker"
        self.vprint(0, "MQTT client connected")
        for t in self.db.topics:
            client.subscribe(t, qos=2)
            self.vprint(1, "Subscribed to topic \"{}\"".format(t))
            self.publishTopicUpdates(t)

    def on_message(self, client, userdata, msg):
        "MQTT client callback on received message"
        self.vprint(1, "RX: {0.topic:s} -> {0.payload:s}".format(msg))
        tid = None
        try:
            payload = json.loads(msg.payload)
            if type(payload) is list:
                tid = self.db.update(msg.topic, *payload)
            elif type(payload) is dict:
                tid = self.db.update(msg.topic, **payload)
            elif type(payload) in (int, float):
                tid = self.db.update(msg.topic, increment=payload)
        except Exception as e:
            self.eprint(e)
        else:
            self.publishTopicUpdates(tid)

    def __init__(self, clientID, database, http_port, verbosity=0):
        """Initalize the counter DB service
        @param clientID The MQTT client ID for this node
        @param database File path name for the peristant dabase file
        @param http_port Port to open web interface on
        @param verbosity How much debug printing to do
        """
        self.client = mqtt.Client(clientID, not clientID)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.verbose = verbosity
        self.db = CounterDB(database)
        
    def doSchedulePublications(self, schedule):
        "Publishes updates for the given schedule"
        self.vprint(2, "Schedule publications for {}".format(schedule))
        for queryTopic, publishTopic, query in self.db.getSchedulePublications(schedule):
            self.vprint(2, "Publishing update for \"{}\"".format(publishTopic))
            self.vprint(3, "\tquery = {}".format(query))
            result = json.dumps(self.db.query(query))
            self.vprint(3, "\tresult = {}".format(result))
            client.publish(publishTopic, result, qos=1, retain=True)
    
    def timerRun(self, exitEvent):
        lastTime = time.localtime()
        while exitEvent.wait(60.0) is False:
            newTime = time.localtime()
            if newTime.tm_min != lastTime.tm_min:
                self.doSchedulePublications(self.db.MINUTELY)
            if newTime.tm_hour != lastTime.tm_hour:
                self.doSchedulePublications(self.db.HOURLY)
            if newTime.tm_yday != lastTime.tm_yday:
                self.doSchedulePublications(self.db.DAILY)
            if newTime.tm_wday < lastTime.tm_wday: # Week has rolled over
                self.doSchedulePublications(self.db.WEEKLY)
            if newTime.tm_mon != lastTime.tm_mon:
                self.doSchedulePublications(self.db.MONTHLY)
            lastTime = newTime
    
def run(self, service, mqttConnectArgs, app, appRunOptions={}, noMQTT=False, noHTTP=False):
    """Lifecycle for all the threads"""
    service.client.loop_start()
    if not noMQTT:
        service.client.connect(*mqttConnectArgs)
    exitEvent = threading.Event()
    timerThread = threading.Thread(target=service.timerRun, args=(exitEvent,))
    service.timerThread.start()
    # App.run is the main thread
    if not noHTTP:
        app.run(**appRunOptions)
    else:
        try:
            while True: time.sleep(60.0) 
        except:
            pass
    # After app.run exits, we tear down
    exitEvent.set()
    service.client.loop_stop()




if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("database",  type=str, help="Where to load/store persistant data")
    parser.add_argument("-i", "--clientID", type=str, default="", help="MQTT client ID for the counter node")
    parser.add_argument("-b", "--brokerHost", type=str, default="localhost", help="MQTT Broker hostname or IP address")
    parser.add_argument('-p', "--brokerPort", type=int, help="MQTT Broker port")
    parser.add_argument('-k', "--brokerKeepAlive", type=int, help="MQTT keep alive seconds")
    parser.add_argument('-n', "--bind", type=str, help="Local interface to bind to for connection to broker")
    parser.add_argument('-w', "--http_port", type=int, default=5000, help="Which port to open web interface on")
    parser.add_argument('-v', "--verbose", action="count", help="Increase debugging verbosity")
    parser.add_argument("--dev_no_mqtt", action="store_true", help="Don't connect to MQTT broker, for testing only.")
    parser.add_argument("--dev_no_http", action="store_true", help="Don't set up HTTP server, for testing only.")
    args = parser.parse_args()
    brokerConnect = [args.brokerHost]
    if args.brokerPort: brokerConnect.append(args.brokerPort)
    if args.brokerKeepAlive: brokerConnect.append(args.brokerKeepAlive)
    if args.bind: brokerConnect.append(args.bind)
    
    global counter
    counter = CounterService(args.clientID, args.database, args.http_port, args.verbose)
    app = flask.Flask(__name__)
    run(counter, brokerConnect, app, {'port'=args.http_port}, args.dev_no_mqtt, args.dev_no_http)
