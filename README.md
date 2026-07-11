AI Security Camera System Requirements
======================================

**Tech Stack**

1) Decide on what facial recognition model we're going to use -> **Deepface** -> [Github Repo](https://github.com/serengil/deepface)
2) Decide how we're going to augment the faces -> Ask user for 5 starting images, augment 6 times, then from there whenever the camera detects the person in production/active deployment, it takes a photo and add it to the dataset. confidence level should be atleast 80%.
3) Decide what web server to use, eg. flask, node, django, springboot, etc. -> **Flask**
4) Decide what database to use, eg. PostgreSQL, SQLite, MongoDB, etc. -> **SQLite**

**Implementation**

1) Decide what pages we need to have on the website -> Dashboard with ability to upload images of person's face. Show live camera feeds for all cameras, show user a live log of all actions, people detected, etc. Nice to have would be viewing past videos
2) Figure out how we want to structure our log files for when a person is detected -> date, time, name, attach the file location of a photo taken at the moment of detection
3) Decide if we want to use our phones' BLE/RFID signatures to be used as our "ID" or if we just want to make like a piece of paper or something -> Try to setup BLE/RFID signatures, fallback to image based ID reconization if previous is not viable
4) Decide how we're going to send notifications, mobile app or email/text notifications -> Ideally, app, but if not enough time, text, if text not viable, fallback to email
5) Decided how we're going to setup p2p connection for redundancy -> Not sure yet, will look into
