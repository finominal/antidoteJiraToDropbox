import os
import requests
import json
import dropbox
import sys
import threading
import time
import logging
from os import walk
from dataclasses import dataclass
from datetime import datetime


#from util.utils import get_keyvault_secret

#secrets/env
userJira = "production@antidote.com.au"
keyJira = "DQoADgLH6p1KaatHWGyQ909C"
dbAppkey = "6ujo80qcw6sy4zk"
dbAppSecret = "ush0ui2khvjgj92"
dbAccessToken = "Gpw-anEq8LcAAAAAAAAAAfYIj9oInmdE8Tk0h0Vtns25OF9xjkUAiYOJ5VeE1hn1"

fileCacheDir = "./fileCache/"

jiraFileDirectory = "./jiraticketsnew"
processedFileDirectory = "./jiraticketsprocessed"
heartbeatUrl = "abc"

workerThread = threading.Thread()

@dataclass
class JiraAttachment:
    ticketNumber: str
    filename: str
    url: str
    fileRaw: bytes
    expectedSize: int

#digital ocean 
#mart@antidote.com.au: #y47GatcNMq3iyan
#https://antidotebiomedical.atlassian.net/browse/AB-74
# production@antidote.com.au|DQoADgLH6p1KaatHWGyQ909C
#jira token header https://developer.atlassian.com/server/jira/platform/basic-authentication/

def SendHeartBeat(url):
    #httpGet(url)
    print(" SentHeartbeat")

##### WORKER THREAD LOOP
# Everything after this will go into a worker in a thread. 
def ProcessNewTickets():
    result = False
    filenames = next(walk(jiraFileDirectory), (None, None, []))[2]  # [] if no file

    for filename in  filenames:
        fullFileName =  jiraFileDirectory + "/" + filename
        print("Opening " + fullFileName)
        with open(fullFileName) as ticket:
            result = processJiraCreated( json.loads(ticket.read()))
        if(result): #move file if successfull
            timeStr = datetime.now().strftime("%m%d%Y%H%M%S")
            os.rename(jiraFileDirectory +"/"+ filename, processedFileDirectory +"/"+ timeStr +"_" + filename)

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
def createDirectories():
    #Create save directory 
    if(not os.path.isdir(jiraFileDirectory)):
        os.mkdir(jiraFileDirectory)

    #Create processed directory
    if(not os.path.isdir(processedFileDirectory)):
        os.mkdir(processedFileDirectory)

def run_job():
    createDirectories()
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