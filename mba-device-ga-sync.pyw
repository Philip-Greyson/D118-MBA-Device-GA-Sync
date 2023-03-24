# Needs the google-api-python-client, google-auth-httplib2 and the google-auth-oauthlib
# pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib


# importing modules
import oracledb  # used to connect to PowerSchool database
import datetime  # used to get current date for course info
import os  # needed to get environement variables
from datetime import *

# google module imports
import json
from re import A
from typing import get_type_hints

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

un = 'PSNavigator' #PSNavigator is read only, PS is read/write
pw = os.environ.get('POWERSCHOOL_DB_PASSWORD') #the password for the PSNavigator account
cs = os.environ.get('POWERSCHOOL_PROD_DB') #the IP address, port, and database name to connect to


# Google API Scopes that will be used. If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/admin.directory.device.chromeos']

# Get credentials from json file, ask for permissions on scope or use existing token.json approval, then build the "service" connection to Google API
creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

service = build('admin', 'directory_v1', credentials=creds)

print("Username: " + str(un) + " |Password: " + str(pw) + " |Server: " + str(cs)) #debug so we can see where oracle is trying to connect to/with


Disabled_Statuses = ['Lost/Stolen']
Enabled_Statuses = ['Ready to Deploy', 'In Use in Classroom', 'Out to Student', 'Out to Teacher']
Deprovision_Statuses = ['Broken/Needs Repair']

if __name__ == '__main__': # main file execution
    with oracledb.connect(user=un, password=pw, dsn=cs) as con: # create the connecton to the database
        with con.cursor() as cur:  # start an entry cursor
            with open('deviceLog.txt', 'w') as log:
                startTime = datetime.now()
                startTime = startTime.strftime('%H:%M:%S')
                print(f'Execution started at {startTime}')
                print(f'Execution started at {startTime}', file=log)
                # get a list of devices from MBA device table
                cur.execute('SELECT u_mba_device.device_name, u_mba_device.serial_number, u_mba_device_status.name, u_mba_device.device_type FROM u_mba_device LEFT JOIN u_mba_device_status ON u_mba_device.device_statusid = u_mba_device_status.id')
                devices = cur.fetchall()
                for device in devices:
                    if device[3] == "Chromebook": # filter to just Chromebooks
                        name = device[0]
                        serial = device[1]
                        ps_status = device[2]
                        query = f'id:{serial}' # construct a query string for the ID (serial number)
                        if ps_status in Disabled_Statuses:
                            print(f'INFO: Device should be disabled: Device Name: {name} | Device Serial: {serial} | Status: {ps_status}')
                            print(f'INFO: Device should be disabled: Device Name: {name} | Device Serial: {serial} | Status: {ps_status}', file=log)
                            deviceToUpdate = service.chromeosdevices().list(customerId='my_customer',query=query).execute()
                            if deviceToUpdate.get('chromeosdevices'):
                                ga_status = deviceToUpdate.get('chromeosdevices')[0].get('status')
                                ga_device_id = deviceToUpdate.get('chromeosdevices')[0].get('deviceId')
                                if ga_status != 'DISABLED': # only disable if they are not already disabled
                                    print(f'    ACTION: Device is currently {ga_status} and will be disabled: {ga_device_id}')
                                    print(f'    ACTION: Device is currently {ga_status} and will be disabled: {ga_device_id}', file=log)
                                    try:
                                        update = service.chromeosdevices().action(customerId='my_customer', resourceId =ga_device_id, body={'action':'disable'}).execute()
                                    except Exception as er:
                                        print(f'    ERROR: {er}')
                                        print(f'    ERROR: {er}', file=log)
                                else:
                                    print(f'    INFO: Device is already disabled')
                                    print(f'    INFO: Device is already disabled', file=log)
                            #deviceToUpdate = service.chromeosdevices().action(customerId='my_customer',
                        # elif ps_status in Deprovision_Statuses:
                            # print(f'TO DEPROVISION: Device Name: {name} | Device Serial: {serial} | Status: {status}')
                        # elif ps_status in Enabled_Statuses:
                            # print(f'TO ENABLE: Device Name: {name} | Device Serial: {serial} | Status: {status}')
                endTime = datetime.now()
                endTime = endTime.strftime('%H:%M:%S')
                print(f'INFO: Execution ended at {endTime}')
                print(f'INFO: Execution ended at {endTime}', file=log)
                              