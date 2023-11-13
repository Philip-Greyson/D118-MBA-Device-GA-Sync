
# D118-MBA-Device-GA-Sync

Script to take the MBA Device Manager+ Plugin data on Chromebook devices from PowerSchool and use it to deprovision, disable and re-enable devices of certain statuses.
Also moves Chromebook devices checked out to students to the correct student OUs in Google Admin.

## Overview

There are 3 arrays that map the status names from the MBA Device Manager+ plugin to the statuses in Google Admin. These must be identical to the setup in PowerSchool. Any devices in PowerSchool that have a status in the *Disabled_Statuses* array will be disabled (locked) until they changed back to an *Enabled_Statuses* status, when they will be re-enabled. Any having a status in the *Deprovision_Statuses* will be de-provisioned, and will need to be manually re-enrolled after.

The program first retrieves information about all devices in Google Admin using the directory API, then stores the device serial numbers, status, internal Google ID, and its current Organizational Unit (OU) location into dictionaries to refer to later. Doing one big retrieval at the beginning saves a **TON** of time versus doing individual calls for each device later.
Then a query is done on the u_mba_device table to retrieve all non-archived devices, get their names, serial numbers, device types, locations, etc.
It then goes through all devices, only those with the device_type of "Chromebook" are processed further. The script checks to see if the status of the device in Google Admin matches what it should be based on the status definitions, and if not it executes the update via the directory API.
Finally, it then checks the current OU location of the device and determines if it should be moved to the correct building device OU based on the school of the student that it is checked out to. If the device is not checked out to a student (teachers are not included), or the student is inactive, graduated, etc, it will not be moved.

## Requirements

The following Environment Variables must be set on the machine running the script:

- POWERSCHOOL_READ_USER
- POWERSCHOOL_DB_PASSWORD
- POWERSCHOOL_PROD_DB

In addition, an OAuth credentials.json file must be in the same directory as the overall script. This is the credentials file you can download from the Google Cloud Developer Console under APIs & Services > Credentials > OAuth 2.0 Client IDs. Download the file and rename it to credentials.json. When the program runs for the first time, it will open a web browser and prompt you to sign into a Google account that has the permissions to disable, enable, deprovision, and move the devices. Based on this login it will generate a token.json file that is used for authorization. When the token expires it should auto-renew unless you end the authorization on the account or delete the credentials from the Google Cloud Developer Console. One credentials.json file can be shared across multiple similar scripts if desired.
There are full tutorials on getting these credentials from scratch available online. But as a quickstart, you will need to create a new project in the Google Cloud Developer Console, and follow [these](https://developers.google.com/workspace/guides/create-credentials#desktop-app) instructions to get the OAuth credentials, and then enable APIs in the project (the Admin SDK API is used in this project).

## Customization

For customization or use outside of my specific use case at D118, you will want to edit the following variables:

- Disabled_Statuses: add any status names (must match what is in PS MBA Device Manager+) into the array that will disable a device when it matches
- Enabled_Statuses: status names for "normal" enabled state. Will be re-enabled from disabled, and not de-provisioned again though re-provisioning will need to manually be done
- Deprovision_Statuses: status names for devices that should be deprovisioned.
- the line `if device[3] == "Chromebook"` if the devices in MBA Device Manager+ have a different device type other than Chromebook
- properOU: a string that defines the OU the devices should reside in. We have separate OUs for each building, which match up to the building abbreviations in PowerSchool so it is constructed based on the student's building. If this is not the case for you, you should change how this is done.
