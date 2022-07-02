import os
import requests
import json
import dropbox
import sys
import threading
import time
import glob
from dataclasses import dataclass
from datetime import datetime
from boto3 import session

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

#secrets/env
userJira = os.getenv("JIRA_USER") 
keyJira = os.getenv("JIRA_KEY") 
dbAccessToken = os.getenv("DB_ACCESS_TOKEN") 
spaces_name = os.getenv("SPACES_NAME") 
spaces_region = os.getenv("SPACES_REGION") 
jiraNewFileDirectory = os.getenv("DIR_JIRA_NEW") 
processedFileDirectory = os.getenv("DIR_JIRA_PROCESSED") 
destinationRoot = os.getenv("DB_DESTINATION_ROOT")  
chunkSize = int(os.getenv("UPLOAD_CHUNK_SIZE_MB"))

heartbeatUrl = "abc"

chunk_size_antidote = chunkSize * 1024 * 1024 
print("Var Chunk size - " + str(chunkSize))

workerThread = threading.Thread()

destinationFolder = ""

@dataclass
class JiraAttachment:
    ticketNumber: str
    filename: str
    url: str
    fileRaw: bytes
    expectedSize: int
    issueType: str
    summary: str
    customfield_10120: str #used to custom set the folder name 

    def getDestinationFilename(self) -> str:
        return "/" + self.issueType.strip() + "/" + self.ticketNumber + "_" +  self.customfield_10120.strip() + "/" + self.filename.strip()

def SendHeartBeat(url):
    #httpGet(url)
    print(" SentHeartbeat")

##### WORKER THREAD LOOP
# Everything after this will go into a worker in a thread. 
def ProcessNewTickets():

    PrepareTempDirectory() #create/clear

    filenames = s3_list_files(spaces_name, jiraNewFileDirectory)

    for filename in filenames:
        print("Retrieving " + filename)
        try:
            s3_download_file(spaces_name, filename)

            with open(filename) as ticket:
            
                content = ticket.read()
                jsonContent = json.loads( content )
                result = processJiraAttachments( jsonContent )

                if(result): #move file if successfull
                    timeStr = datetime.now().strftime("%Y%m%d%H%M%S")
                    leafFileName = path_leaf(filename)
                    s3_upload_file(spaces_name, filename, processedFileDirectory + "/" + timeStr + "_" +  leafFileName) 
                    s3_delete_file(spaces_name, filename)

        except Exception as e :
            print("Exception protocessing ticket " + filename + " Deleting this webhook notice. EXCEPTION " + str(e))
            s3_delete_file(spaces_name, filename)

        os.remove(filename) #remove the local file

def PrepareTempDirectory():
    if os.path.exists(jiraNewFileDirectory):
        files = glob.glob(jiraNewFileDirectory + "/*")
        for f in files:
            os.remove(f)
    else :
        os.mkdir(jiraNewFileDirectory)
  
def path_leaf(path):
    return os.path.split(path)[1]

#Orchestrator
def processJiraAttachments(jiraMetaData):
    print ('ProcessJira')
    restultInfo = ""
    attachments = extractJiraAttachmentsFromMetadata(jiraMetaData)
    for attachment in attachments:

        if(not dbFileExists( attachment)): #already uploaded?
            a = getJiraAttachment(attachment) #download attachment from Jira
            pushToDropBox(a) 
            restultInfo += "Uploaded " + a.getDestinationFilename() + " | "
        else:
            restultInfo += "File exists " + attachment.getDestinationFilename() + " | "
    
    restultInfo += "Completed!"
    print(restultInfo)
    #result into to log file?
    return True

def pushToDropBox(jiraAttachment):
    destinationPath = destinationRoot + jiraAttachment.getDestinationFilename()
    dbUploadBytes(dbAccessToken, jiraAttachment.fileRaw, destinationPath)

#Jira 
def getJiraAttachment(attachmentMetadata):
    print('GET ' + attachmentMetadata.url )
    print('Expected Size ' + str(attachmentMetadata.expectedSize) )
    data = httpGetAuth(attachmentMetadata.url, userJira, keyJira)
    attachmentMetadata.fileRaw = data.content
    print('GET ' + attachmentMetadata.url + " OK!")
    return attachmentMetadata

def httpGetAuth(url, username, password):
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
        results.append( JiraAttachment( ticketNo, attachment["filename"], attachment["content"], None ,attachment["size"], jiraData["fields"]["issuetype"]["name"], jiraData["fields"]["summary"], jiraData["fields"]["customfield_10120"]) )
        print('extractJiraAttachmentMetadata ' + attachment["content"])
    return results

#Dropbox
#https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html?highlight=upload#dropbox.dropbox_client.Dropbox.files_upload_session_start

#doesFileExist
def dbFileExists(attachment):
    root = ""
    filename = destinationRoot + attachment.getDestinationFilename()
    with dropbox.Dropbox(dbAccessToken, 30) as dbx:
        try:
            results = dbx.files_search(root,filename)
            if len(results.matches) > 0:
                    for match in results.matches:
                        if match.metadata.path_display == attachment.fileName:
                            return True
        except Exception as e:
            print("Catch - Directory does not exist? " + str(e))
            
    return False

#upload bytes
def dbUploadBytes(
    access_token,
    file,
    target_path,
    timeout=900,
    chunk_size=chunk_size_antidote,
):
    dbx = dropbox.Dropbox(access_token, timeout=timeout)
    print("Dropbox Upload Initiated")
    print("Chunk size - " + str(chunk_size_antidote))
    print("target_path: "+ target_path)

    file_size = sys.getsizeof(file)
    print("Upload to Dropbox: " + target_path + " Size:" + str(file_size) )

    if file_size <= chunk_size:
        print("Small File - Direct Upload")
         
        print(dbx.files_upload(file, target_path))
    else: 
        print("Large file = Session Upload")
        location = 0
        upload_session_start_result = dbx.files_upload_session_start(
            file[location:location + chunk_size]
        )

        print("Session Started: " + upload_session_start_result.session_id)
        cursor = dropbox.files.UploadSessionCursor(
            session_id=upload_session_start_result.session_id,
            offset = chunk_size,
        )

        commit = dropbox.files.CommitInfo(path=target_path)
        location =+ chunk_size
        
        while location < file_size:
            if (file_size - location) <= chunk_size:
                print( "sessionFinished: " +
                    str(dbx.files_upload_session_finish(
                        file[location:file_size-1], cursor, commit) #watch this for errors on closing file
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
                
                location += chunk_size #for getting a subset of the data array
                cursor.offset += chunk_size #tells dropbox where we are in the file

def s3_list_files( space_name, directory):
    
    bucket = s3resource.Bucket(name=space_name)
    results = []
    
    for obj in bucket.objects.all():
        results.append(obj.key)

    filtered = list(filter(lambda k: directory in k, results))
    return  filtered

def s3_download_file(space_name, file_name):
    try:
        #s3resource.meta.client.download_file(space_name, file_name, file_name)
        s3resource.Bucket(space_name).download_file(file_name, file_name)
        message = "Success"
        return message
        # pass
    except Exception as e:
        message = "Error occured downloading file " + file_name + " " + str(e)

    return message

def s3_upload_file(space_name, local_file, upload_name):
    try:
        s3resource.meta.client.upload_file(local_file, space_name, upload_name)
        message = "Success"
        return message
        # pass
    except Exception as e:
        message = "Error occured uloading file " + upload_name + " " + str(e)

    return message

def s3_delete_file(space_name, file_name):
    try:
        s3resource.Object(space_name, file_name).delete()
        message = "Success"
        return message
        # pass
    except Exception as e:
        message = "Error occured deleting file " + file_name + " " + str(e)

    return message
   

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
    thread.join()