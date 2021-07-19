import os
import flask
from flask import request
from spaces import spaces

#from util.utils import get_keyvault_secret

app = flask.Flask(__name__)
app.config["DEBUG"] = False


#secrets/env
userJira = "production@antidote.com.au"
keyJira = "DQoADgLH6p1KaatHWGyQ909C"

spaces_name = "antidote-jira-metadata-store"
spaces_region = "sfo3" #"sfo3.digitaloceanspaces.com"

jiraFileDirectory = "jiraticketsnew"

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
@app.route('/healthcheck', methods=['GET'])
def heathcheck():
    return "Health OK!"

#Helpers
def PersistRequstData(requestData, ticketNo):

    uploadFilename = jiraFileDirectory + "/" + ticketNo + ".json"
    localFilename  = "./" + uploadFilename

    open(localFilename, "wb").write(requestData) #stream to file

    result = spaces.upload_file(spaces_name, spaces_region, localFilename, uploadFilename)

    if result == "Success":
        os.remove(localFilename)

def createDirectories():
    #Create save directory 
    if(not os.path.isdir(jiraFileDirectory)):
        os.mkdir(jiraFileDirectory)

# Lets Go!
#app.run(host="0.0.0.0", port=8080)
app.run(host="127.0.0.1", port=8080)
