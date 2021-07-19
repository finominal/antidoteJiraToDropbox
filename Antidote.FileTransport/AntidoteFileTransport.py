import os
import requests
import json
import dropbox
import sys
import threading
import time
import logging
from spaces import spaces
from dataclasses import dataclass
from datetime import datetime
from boto3 import session
from botocore.client import Config
from boto3.s3.transfer import S3Transfer

ACCESS_ID = str("THJ2HKRSFAH6RTJ6W43O")
SECRET_KEY = str("NWgzBh1kBJqgGyJL99AZ0tI8HjGryPRyw4CRm8OwLYY")
REGION = str("sfo3")

s3sesseion = session.Session()
s3resource = s3sesseion.resource('s3',
                        region_name=REGION,
                        endpoint_url='https://'+REGION+'.digitaloceanspaces.com',
                        aws_access_key_id=ACCESS_ID,
                        aws_secret_access_key=SECRET_KEY)

#secrets/env
userJira = "production@antidote.com.au"
keyJira = "DQoADgLH6p1KaatHWGyQ909C"

dbAppkey = "6ujo80qcw6sy4zk"
dbAppSecret = "ush0ui2khvjgj92"
dbAccessToken = "Gpw-anEq8LcAAAAAAAAAAfYIj9oInmdE8Tk0h0Vtns25OF9xjkUAiYOJ5VeE1hn1"

jiraNewFileDirectory = "jiraticketsnew"
processedFileDirectory = "jiraticketsprocessed"

heartbeatUrl = "abc"

spaces_name = "antidote-jira-metadata-store"
spaces_region = "sfo3" #"sfo3.digitaloceanspaces.com"

workerThread = threading.Thread()

@dataclass
class JiraAttachment:
    ticketNumber: str
    filename: str
    url: str
    fileRaw: bytes
    expectedSize: int

def SendHeartBeat(url):
    #httpGet(url)
    print(" SentHeartbeat")

##### WORKER THREAD LOOP
# Everything after this will go into a worker in a thread. 
def ProcessNewTickets():
    result = False

    #filenames = next(walk(jiraFileDirectory), (None, None, []))[2]  # [] if no file
    filenames = list_files( spaces_name, jiraNewFileDirectory)

    for filename in filenames:
        print("Retrieving " + filename)
        download_file(spaces_name, filename)

        with open(filename) as ticket:
            result = processJiraCreated( json.loads( ticket.read() ) )

            if(result): #move file if successfull
                timeStr = datetime.now().strftime("%m%d%Y%H%M%S")

                leafFileName = path_leaf(filename)
                spaces.upload_file(spaces_name, spaces_region,ticket, processedFileDirectory + "/" + timeStr + leafFileName)

                spaces.delete_file(spaces_name, spaces_region, filename)

                os.remove(filename) #remove the local file

def path_leaf(path):
    return os.path.split(path)[1]

#Orchestrator
def processJiraCreated(jiraMetaData):
    print ('ProcessJira')
    restultInfo = ""
    attachments = extractJiraAttachmentsFromMetadata(jiraMetaData)
    for attachment in attachments:

        if(not dbFileExists( attachment.ticketNumber, attachment.filename )): #already uploaded?
            a = getJiraAttachment(attachment) #download attachment from Jira
            pushToDropBox(a) 
            restultInfo += "Uploaded " + attachment.ticketNumber + "/" + a.filename + " | "
        else:
            restultInfo += "File exists " + attachment.ticketNumber + "/" + attachment.filename  + " | "
    restultInfo += "Completed!"
    print(restultInfo)
    #result into to log file?
    return True

def pushToDropBox(jiraAttachment):
    destinationPath = "/" + jiraAttachment.ticketNumber + "/" + jiraAttachment.filename
    dbUploadBytes(dbAccessToken, jiraAttachment.fileRaw, destinationPath)

#Jira 
def getJiraAttachment(attachmentMetadata):
    print('GET ' + attachmentMetadata.url )
    data = httpGet(attachmentMetadata.url, userJira, keyJira)
    attachmentMetadata.fileRaw = data.content
    print('GET ' + attachmentMetadata.url + " OK!")
    return attachmentMetadata

def httpGet(url, username, password):
    r = requests.get(url, auth=(username,password))
    r.raise_for_status() 
    return r

def httpGet(url):
    r = requests.get(url)
    r.raise_for_status() 
    return r

def extractJiraAttachmentsFromMetadata(jiraData):
    results = []
    ticketNo = jiraData["key"]
    for attachment in jiraData["fields"]["attachment"]:
        results.append( JiraAttachment( ticketNo, attachment["filename"], attachment["content"], None ,attachment["size"] ) )
        print('extractJiraAttachmentMetadata ' + attachment["content"])
    return results

#Dropbox
#https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html?highlight=upload#dropbox.dropbox_client.Dropbox.files_upload_session_start

#doesFileExist
def dbFileExists(directory, filename):
    root = "" 
    file = "/" + directory + "/" + filename
    with dropbox.Dropbox(dbAccessToken, 30) as dbx:
        results = dbx.files_search(root,filename)
        if len(results.matches) > 0:
                for match in results.matches:
                    if match.metadata.path_display == file:
                        return True
    return False

#upload bytes
def dbUploadBytes(
    access_token,
    file,
    target_path,
    timeout=900,
    chunk_size=4 * 1024 * 1024,
):
    dbx = dropbox.Dropbox(access_token, timeout=timeout)
    print("Dropbox Handler Initiated")

    file_size = sys.getsizeof(file)
    chunk_size = 4 * 1024 * 1024
    print("Upload to Dropbox: " + target_path + " Size:" + str(file_size) )

    if file_size <= chunk_size:
        print("Small File - Direct Upload")
        print(dbx.files_upload(file.read(), target_path))
    else: 
        print("Large file = Session Upload")
        location = 0
        upload_session_start_result = dbx.files_upload_session_start(
            file[location:chunk_size]
        )

        location += chunk_size

        print("Session Started: " + upload_session_start_result.session_id)
        cursor = dropbox.files.UploadSessionCursor(
            session_id=upload_session_start_result.session_id,
            offset = location,
        )

        commit = dropbox.files.CommitInfo(path=target_path)

        while location < file_size:
            if (file_size - location) <= chunk_size:
                print( "sessionFinished: " +
                    str(dbx.files_upload_session_finish(
                        file[location:file_size - location], cursor, commit) #watch this for errors on closing file
                        )
                )
                print("F Loction: " + str(location) )
            else:
                print("Append - cursor.offset " + str(cursor.offset))
                dbx.files_upload_session_append( 
                    file[location:location + chunk_size],
                    cursor.session_id,
                    cursor.offset,
                )

            location += chunk_size
            cursor.offset = location

#Helpers
# def createDirectories():
#     #Create save directory 
#     if(not os.path.isdir(jiraNewFileDirectory)):
#         os.mkdir(jiraNewFileDirectory)

#     #Create processed directory
#     if(not os.path.isdir(processedFileDirectory)):
#         os.mkdir(processedFileDirectory)


def list_files( space_name, directory):
    bucket = s3resource.Bucket(name=space_name)
    results = []
    
    for obj in bucket.objects.all():
        results.append(obj.key)

    filtered = list(filter(lambda k: directory in k, results))
    return  filtered

def download_file(space_name, file_name):
    s3resource.Object(space_name, file_name).download_file(
    f'/tmp/{file_name}') # Python 3.6+

def upload_file(space_name, local_file, upload_name):
    try:
        s3resource.upload_file(local_file, space_name, upload_name)
        message = "Success"
        return message
        # pass
    except Exception as e:
        message = "Error occured. Check Space name, etc"

    return message
    #upload_file('my-space-name', 'sfo2', 'test.txt', 'me1.txt')


#main Loop
def run_job():
    #createDirectories()
    while True: 
        try:
            print("Worker running: " + datetime.utcnow().strftime('%B %d %Y - %H:%M:%S'))
            SendHeartBeat(heartbeatUrl)
            ProcessNewTickets()
            time.sleep(10)  
        except AssertionError as error:
            print('Exception Thrown '+ datetime.utcnow().strftime('%B %d %Y - %H:%M:%S ' ))
            print(error)

#Start the APP
if ( workerThread.is_alive() == False): #start/restart the worker
    thread = threading.Thread(target=run_job)
    thread.start() 