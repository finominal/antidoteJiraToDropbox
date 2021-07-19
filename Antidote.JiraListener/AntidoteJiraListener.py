import os
import flask
from boto3 import session
from flask import request

#from util.utils import get_keyvault_secret

ACCESS_ID = str("THJ2HKRSFAH6RTJ6W43O")
SECRET_KEY = str("NWgzBh1kBJqgGyJL99AZ0tI8HjGryPRyw4CRm8OwLYY")
spaces_name = "antidote-jira-metadata-store"
spaces_region = "sfo3" #"sfo3.digitaloceanspaces.com"

s3sesseion = session.Session()

def getS3Resource() :
    return  s3sesseion.resource('s3',
                    region_name=spaces_region,
                    endpoint_url='https://'+spaces_region+'.digitaloceanspaces.com',
                    aws_access_key_id=ACCESS_ID,
                    aws_secret_access_key=SECRET_KEY)

app = flask.Flask(__name__)
app.config["DEBUG"] = False

#secrets/env
userJira = "production@antidote.com.au"
keyJira = "DQoADgLH6p1KaatHWGyQ909C"


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

    result = upload_file(spaces_name, localFilename, uploadFilename)

    if result == "Success":
        os.remove(localFilename)

def createDirectories():
    #Create save directory 
    if(not os.path.isdir(jiraFileDirectory)):
        os.mkdir(jiraFileDirectory)

def upload_file(space_name, local_file, upload_name):
    s3  = getS3Resource()
    try:
        s3.meta.client.upload_file(local_file, space_name, upload_name)
        message = "Success"
        return message
        # pass
    except Exception as e:
        message = "Error occured uloading file " + upload_name + " " + str(e)

    return message
    #upload_file('my-space-name', 'sfo2', 'test.txt', 'me1.txt')


# Lets Go!
app.run(host="0.0.0.0", port=8080)