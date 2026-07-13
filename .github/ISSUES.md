# Suggested Issues

Assign 2-3 issues per teammate. Each issue is intentionally big enough to own, test, and demo.

## Recognition pipeline

1. DeepFace enrollment database
   - Generate embeddings for enrolled people.
   - Store model name, detector backend, and embedding path.
   - Add a rebuild command for the local face database.

2. Camera frame recognition loop
   - Pull frames from registered RTSP/HTTP cameras.
   - Run DeepFace recognition on intervals.
   - Log detections only when confidence is at least 80%.

3. Face image augmentation
   - Take 5 starting images per person.
   - Generate 6 augmented images per source image.
   - Mark augmented images in SQLite and show counts in dashboard.

## Web app and UI

4. Person profile page
   - Show enrolled images, notes, and detection history.
   - Allow adding/removing images.
   - Add validation for duplicate names and unsupported files.

5. Live camera feed page
   - Show active camera streams.
   - Display camera health and last frame time.
   - Add an inactive/error state for broken streams.

6. Detection review workflow
   - Add filters by person, camera, date, and confidence.
   - Show detection snapshots.
   - Add "mark false positive" support.

## Notifications and devices

7. Email notification fallback
   - Send email when unknown people or selected known people are detected.
   - Add notification settings per person.
   - Include timestamp, camera, confidence, and snapshot.

8. BLE/RFID identity proof of concept
   - Research viable BLE/RFID phone signature options.
   - Build a small scanner prototype.
   - Record whether device signal agrees with face recognition.

9. Mobile/text notification research spike
   - Compare SMS, push notification, and email options.
   - Build one working minimal notification route.
   - Document cost, setup steps, and privacy concerns.

## Reliability and deployment

10. Video clip archive
    - Save short clips around each detection event.
    - Link archived clips from the detection log.
    - Add cleanup rules for old clips.

11. Peer-to-peer redundancy research
    - Research whether P2P is realistic for the project timeline.
    - Prototype camera node heartbeat between two machines.
    - Write a short recommendation.

12. Testing and developer setup
    - Add pytest coverage for routes and database helpers.
    - Add sample seed data command.
    - Add a one-command setup script.

13. Security and privacy hardening
    - Validate upload type and size.
    - Prevent unsafe filenames and private path leakage.
    - Add a simple data deletion workflow.

14. Deployment packaging
    - Add Dockerfile for the Flask app.
    - Document required environment variables.
    - Test fresh setup on another machine.

15. Authentication and roles
    - Add login/logout for dashboard users.
    - Create admin and viewer roles.
    - Protect people, camera, and detection routes.

16. Dataset quality tools
    - Flag blurry or low-confidence enrollment images.
    - Show per-person dataset completeness.
    - Add guidance when a person needs more images.
