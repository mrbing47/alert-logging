# import the required libraries
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os.path
import base64
from bs4 import BeautifulSoup
from datetime import datetime
import json
import schedule
import time
import pytz


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %z"
UTC = pytz.UTC

OLD_TIME = 0
CURRENT_TIME = UTC.localize(datetime.now().replace(tzinfo=None))
ERROR_CODES = ["ERROR: 404", "ERROR: 403"]

def getEmails(oldEmails):
	creds = None

	if os.path.exists('token.pickle'):
		with open('token.pickle', 'rb') as token:
			creds = pickle.load(token)

	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
			creds = flow.run_local_server(port=0)

		with open('token.pickle', 'wb') as token:
			pickle.dump(creds, token)
	
	print("Connecting to Gmail API")
	service = build('gmail', 'v1', credentials=creds)
	
	print("Fetching results")
	# Here <system@example.com> is the email id Application would be using to send us the email, is passed to the query param "from" which filters the emails..
	# and subject is the query param to filter the emails based on the subject
	result = service.users().messages().list(userId='me', q="from:<system@example.com> subject:error").execute()
	
	print("Retreiving Messages")
	messages = result.get('messages')
	
	
	if messages == None:
		return []
	
	alerts = {}
	
	for msg in messages:
		
		if not msg['id'] in oldEmails:	
			txt = service.users().messages().get(userId='me', id=msg['id']).execute()

			try:
				payload = txt['payload']
				headers = payload['headers']


				log = {}
				isValid = True
				for i in headers:
					if i["name"] == "Subject":
						if not i['value'] in ERROR_CODES:
							isValid = False
							break

						log["subject"] = i["value"]
					if i['name'] == 'From':
						log["from"] = i["value"]
					if i["name"] == "Date":
						log["date"] = i["value"]
						strtime = UTC.localize(datetime.strptime(log["date"],DATE_FORMAT).replace(tzinfo=None))
						if OLD_TIME > strtime:
							isValid = False
							break
						
					

				if not isValid:
					continue
	
				data = payload['parts'][0]["body"]["data"]
				body = base64.b64decode(data.replace("-","+").replace("_","/"))
				log['body'] = body.decode("utf-8")
				alerts[msg["id"]] = log
			
			except Exception as e:
				print(e)
	
	
	return alerts


def getJSON():
	fin = open('emails.json')
	data = fin.read()
	fin.close()
	
	if data == '':
		return dict()
	else: 
		return json.loads(data)

def setJSON(data):
	fout = open('emails.json', 'w')
	fout.write(json.dumps(data))
	fout.close()


def script(emails):
	global OLD_TIME
	global CURRENT_TIME

	OLD_TIME = CURRENT_TIME
	CURRENT_TIME = UTC.localize(datetime.now().replace(tzinfo=None))
	
	newEmails = getEmails(oldEmails)
	
	if len(newEmails) > 0:
		emails.update(newEmails)
		setJSON(emails)
		print("Updated the JSON File.\n")
	else:
		print("No new update.\n")



oldEmails = getJSON()
schedule.every(5).minutes.do(script, oldEmails)


while True:
	schedule.run_pending()
	time.sleep(1)
