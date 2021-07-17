import os
import flask
import threading
from flask import request
from dataclasses import dataclass
from datetime import datetime

#from util.utils import get_keyvault_secret

app = flask.Flask(__name__)
app.config["DEBUG"] = True

#secrets/env
userJira = "production@antidote.com.au"
keyJira = "DQoADgLH6p1KaatHWGyQ909C"

fileCacheDir = "./fileCache/"

jiraFileDirectory = "./jiraticketsnew"
processedFileDirectory = "./jiraticketsprocessed"

workerThread = threading.Thread()

#setup
@app.before_first_request #this runs each request. Find a better home
def activate_job():
    createDirectories() #some local file directories are needed. 

#flask routes
@app.route('/', methods=['GET'])
def home():
    return "<h1> Antidote Biomedical </h1> </p> <div> " + str(app.url_map) + "<div>"

@app.route('/api/v1/webhook/jira/createOrUpdate', methods=['POST'])
async def jiraCreate():
    jiraData = request.json
    ticketNo = jiraData["key"]
    PersistRequstData(request.data, ticketNo)
    return "Recieved " + ticketNo

#Helpers
def PersistRequstData(requestData, ticketNo):
    filename  = jiraFileDirectory + "/" + ticketNo + ".json"
    open(filename, "wb").write(requestData) #stream to file

def createDirectories():
    #Create save directory 
    if(not os.path.isdir(jiraFileDirectory)):
        os.mkdir(jiraFileDirectory)

    #Create processed directory
    if(not os.path.isdir(processedFileDirectory)):
        os.mkdir(processedFileDirectory)

# Lets Go!
app.run()
