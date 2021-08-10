import os
import flask
import glob
from boto3 import session
from flask import request

#get environment variables
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY") 
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY") 
SPACES_NAME = os.getenv("SPACES_NAME")  
SPACES_REGION = os.getenv("SPACES_REGION") 

s3sesseion = session.Session()

s3resource = s3sesseion.resource('s3',
                    region_name=SPACES_REGION,
                    endpoint_url='https://'+SPACES_REGION+'.digitaloceanspaces.com',
                    aws_access_key_id=S3_ACCESS_KEY,
                    aws_secret_access_key=S3_SECRET_KEY)

app = flask.Flask(__name__)
app.config["DEBUG"] = False

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
    if checkConfigurations() == False:
        return "Configs Missing!"
    return "Health OK!"

#Helpers
def PersistRequstData(requestData, ticketNo):

    uploadFilename = jiraFileDirectory + "/" + ticketNo + ".json"
    localFilename  = "./" + uploadFilename

    open(localFilename, "wb").write(requestData) #stream to file

    result = upload_file(SPACES_NAME, localFilename, uploadFilename)

    if result == "Success":
        os.remove(localFilename)

def createDirectories():
    if os.path.exists(jiraFileDirectory):
        files = glob.glob(jiraFileDirectory + "/*")
        for f in files:
            os.remove(f)
    else :
        os.mkdir(jiraFileDirectory)

def upload_file(space_name, local_file, upload_name):
    try:
        s3resource.meta.client.upload_file(local_file, space_name, upload_name)
        message = "Success"
        return message
        # pass
    except Exception as e:
        message = "Error occured uloading file " + upload_name + " " + str(e)

    return message
    #upload_file('my-space-name', 'sfo2', 'test.txt', 'me1.txt')

def checkConfigurations():
    if S3_ACCESS_KEY == "":
         print("CONFIGURATION ERROR: S3_ACCESS_KEY not defined")
         return False
    if S3_SECRET_KEY == "":
         print("CONFIGURATION ERROR: S3_SECRET_KEY not defined")
         return False
    if SPACES_NAME == "":
         print("CONFIGURATION ERROR: SPACES_NAME not defined")
         return False
    if SPACES_REGION == "":
         print("CONFIGURATION ERROR: SPACES_REGION not defined")
         return False
    return True
    
# Lets Go!
app.run(host="0.0.0.0", port=8080)