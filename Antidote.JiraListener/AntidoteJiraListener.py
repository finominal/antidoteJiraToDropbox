import os
import flask
from flask import request
import spaces

#from util.utils import get_keyvault_secret

app = flask.Flask(__name__)
app.config["DEBUG"] = False


#secrets/env
userJira = "production@antidote.com.au"
keyJira = "DQoADgLH6p1KaatHWGyQ909C"

space_name = "antidote-jira-metadata-store"
space_region = "sfo3" #"sfo3.digitaloceanspaces.com"

jiraFileDirectory = "jiraticketsnew"
processedFileDirectory = "jiraticketsprocessed"

#setup
@app.before_first_request #this runs each request. Find a better home
def activate_job():
    createDirectories() #some local file directories are needed. 

#flask routes
@app.route('/', methods=['GET'])
def home():
    return "<h1> Antidote Biomedical </h1> </p> <div> " + str(app.url_map) + "<div>"

@app.route('/api/v1/webhook/jira/createOrUpdate', methods=['POST'])
def jiraCreate():
    jiraData = request.json
    ticketNo = jiraData["key"]
    PersistRequstData(request.data, ticketNo)
    return "Recieved " + ticketNo

    #flask routes
@app.route('/heathcheck', methods=['GET'])
def heathcheck():
    return "Health OK!"

#Helpers
def PersistRequstData(requestData, ticketNo):
    filename  = "./" + jiraFileDirectory + "/" + ticketNo + ".json"
    open(filename, "wb").write(requestData) #stream to file
    spaces.upload_file(space_name, space_region, filename,  ticketNo + ".json")

def createDirectories():
    #Create save directory 
    if(not os.path.isdir(jiraFileDirectory)):
        os.mkdir(jiraFileDirectory)

    #Create processed directory
    if(not os.path.isdir(processedFileDirectory)):
        os.mkdir(processedFileDirectory)

# Lets Go!
app.run(host="0.0.0.0", port=8080)
