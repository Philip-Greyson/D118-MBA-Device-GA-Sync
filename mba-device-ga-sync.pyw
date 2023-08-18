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

                # get a list of every device in our google admin (takes a while), put the status and device id into dictonaries by the device serial number
                deviceListToken = '' # blank primer for multi-page query results
                deviceStatusDict = {} # dict holding the status for all serial numbers
                deviceIDDict = {} # dict holding the google admin internal ID for the devices by serial number
                print('Compiling list of all devices in Google Admin, this may take a while')
                print('Compiling list of all devices in Google Admin, this may take a while', file=log)

                deviceResults = service.chromeosdevices().list(customerId='my_customer',projection='BASIC').execute()
                while deviceListToken is not None:
                    if deviceListToken == '':
                        deviceResults = service.chromeosdevices().list(customerId='my_customer',projection='BASIC').execute() # first time run, it doesnt like having any pageToken defined for some reason
                    else:
                        deviceResults = service.chromeosdevices().list(customerId='my_customer',pageToken=deviceListToken,projection='BASIC').execute() # subsequent runs with the pageToken defined

                    deviceListToken = deviceResults.get('nextPageToken')
                    devices = deviceResults.get('chromeosdevices', []) # separate just the devices list from the rest of the result
                    for device in devices:
                        status = device.get('status')
                        deviceId = device.get('deviceId')
                        serial = device.get('serialNumber')
                        deviceStatusDict.update({serial: status}) # add the serial : status entry to the dict
                        deviceIDDict.update({serial : deviceId}) # add the serial : device ID to the dict

    
                # print(deviceStatusDict, file=log) # debug
                # print(deviceIDDict, file=log) # debug
                print('Starting processing of devices from MBA Device Manager')
                print('Starting processing of devices from MBA Device Manager', file=log)

                # get a list of devices from MBA device table
                cur.execute('SELECT u_mba_device.device_name, u_mba_device.serial_number, u_mba_device_status.name, u_mba_device.device_type, u_mba_device.archived, u_mba_device_location.name, u_mba_device_location.parent_locationid FROM u_mba_device LEFT JOIN u_mba_device_status ON u_mba_device.device_statusid = u_mba_device_status.id LEFT JOIN u_mba_device_location ON u_mba_device.locationid = u_mba_device_location.id ORDER BY u_mba_device_location.id') # do a query for the device name, serial, status, device type, location name, and parent location id and archive status from the mba tables
                devices = cur.fetchall()
                for device in devices:
                    if device[3] == "Chromebook" and device[4] != 1: # filter to just non-archived Chromebooks
                        name = device[0]
                        serial = device[1]
                        ps_status = device[2]
                        ga_status = deviceStatusDict.get(serial) # get the status of the device in Google Admin
                        location_name = str(device[5])
                        location_parent_id = str(device[6])

                        if location_parent_id is None or location_parent_id == "None": # if there is no parent_locationid for the location, it is a building already
                            location = location_name # so just set the name of the location as the location
                        elif location_parent_id:
                            # print(f'LOCATION-PARENT-ID={location_parent_id}') #debug
                            cur.execute('SELECT name FROM u_mba_device_location WHERE id = ' + location_parent_id)
                            location = cur.fetchall()[0][0] # get the first result, there should only be one
                        else:
                            location = 'ERROR'

                        if ga_status: # if we found a match for the serial in the dictionary we can continue, otherwise need to throw an error for device not found

                            if ps_status in Disabled_Statuses:
                                print(f'INFO: Device should be disabled: Device Name: {name} | Device Serial: {serial} | PS Status: {ps_status}')
                                # print(f'INFO: Device should be disabled: Device Name: {name} | Device Serial: {serial} | PS Status: {ps_status}', file=log)
                                ga_device_id = deviceIDDict.get(serial)
                                if ga_status != 'DISABLED' and ga_status != 'DEPROVISIONED': # only disable if they are not already disabled, and cant do any actions on already deprovisioned devices until they get re-enrolled
                                    print(f'    ACTION: Device {serial}at {location} is currently {ga_status}, marked as "{ps_status}" in PS, and will be disabled. GA ID: {ga_device_id}')
                                    print(f'ACTION: Device {serial} at {location} is currently {ga_status}, marked as "{ps_status}" in PS, and will be disabled. GA ID: {ga_device_id}', file=log)
                                    ga_device_id = deviceIDDict.get(serial)
                                    try:
                                        print() # blank line so it can run without making changes
                                        # update = service.chromeosdevices().action(customerId='my_customer', resourceId =ga_device_id, body={'action':'disable'}).execute()
                                    except Exception as er:
                                        print(f'    ERROR: {er}')
                                        print(f'    ERROR: {er}', file=log)
                                else:
                                    print(f'    INFO: Device is already disabled')
                                    # print(f'    INFO: Device is already disabled', file=log)
                                
                                    
                            elif ps_status in Deprovision_Statuses:
                                print(f'INFO: Device should be deprovisioned: Device Name: {name} | Device Serial: {serial} | PS Status: {ps_status}')
                                # print(f'INFO: Device should be deprovisioned: Device Name: {name} | Device Serial: {serial} | PS Status: {ps_status}', file=log)
                                ga_device_id = deviceIDDict.get(serial)
                                if ga_status != 'DEPROVISIONED': # only deprovision if they are not already deprovisioned
                                    print(f'    ACTION: Device {serial} at {location} is currently {ga_status}, marked as "{ps_status}" in PS, and will be deprovisioned. GA ID: {ga_device_id}')
                                    print(f'ACTION: Device {serial} at {location} is currently {ga_status}, marked as "{ps_status}" in PS, and will be deprovisioned. GA ID:{ga_device_id}', file=log)
                                    try:
                                        print() # blank line so it can run without making changes
                                        # update = service.chromeosdevices().action(customerId='my_customer', resourceId =ga_device_id, body={'action':'deprovision'}).execute()
                                    except Exception as er:
                                        print(f'    ERROR: {er}')
                                        print(f'    ERROR: {er}', file=log)
                                else:
                                    print(f'    INFO: Device is already deprovisioned')
                                    # print(f'    INFO: Device is already deprovisioned', file=log)

                            elif ps_status in Enabled_Statuses:
                                print(f'INFO: Device should be activated: Device Name: {name} | Device Serial: {serial} | PS Status: {ps_status}')
                                # print(f'INFO: Device should be activated: Device Name: {name} | Device Serial: {serial} | PS Status: {ps_status}', file=log)
                                ga_device_id = deviceIDDict.get(serial)
                                if ga_status != 'ACTIVE' and ga_status != 'DEPROVISIONED': # only activate if they are not already active (disabled), also can't do anything to deprovisioned devices until re-enrolled
                                    print(f'    ACTION: Device {serial} at {location} is currently {ga_status}, marked as "{ps_status}" in PS, and will be re-enabled. GA ID: {ga_device_id}')
                                    print(f'ACTION: Device {serial} at {location} is currently {ga_status}, marked as "{ps_status}" in PS, and will be re-enabled. GA ID:{ga_device_id}', file=log)
                                    try:
                                        print() # blank line so it can run without making changes
                                        # update = service.chromeosdevices().action(customerId='my_customer', resourceId =ga_device_id, body={'action':'reenable'}).execute()
                                    except Exception as er:
                                        print(f'    ERROR: {er}')
                                        print(f'    ERROR: {er}', file=log)
                                else:
                                    print(f'    INFO: Device is already activated')
                                    # print(f'    INFO: Device is already activated', file=log)
                        else:
                            print(f'ERROR: Device {serial} at {location} not found in Google Admin.')
                            print(f'ERROR: Device {serial} at {location} not found in Google Admin.', file=log)
                endTime = datetime.now()
                endTime = endTime.strftime('%H:%M:%S')
                print(f'INFO: Execution ended at {endTime}')
                print(f'INFO: Execution ended at {endTime}', file=log)
                              