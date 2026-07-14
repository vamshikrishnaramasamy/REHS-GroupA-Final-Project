import depthai as dai
import subprocess
import time

# 1. Setup the DepthAI Pipeline Context
with dai.Pipeline() as pipeline:
    
    # Define source using the v3 Camera node and build it
    cam_rgb = pipeline.create(dai.node.Camera).build()
    
    # Request a clean 1080p output stream directly from the camera component
    video_out = cam_rgb.requestOutput(size=(1920, 1080), type=dai.ImgFrame.Type.NV12)

    # Define hardware encoder node
    video_enc = pipeline.create(dai.node.VideoEncoder)
    video_enc.setDefaultProfilePreset(30, dai.VideoEncoderProperties.Profile.H264_MAIN)

    # Link camera output to encoder input
    video_out.link(video_enc.input)

    # Build the host communication queue directly from the encoder output stream
    video_queue = video_enc.bitstream.createOutputQueue(maxSize=30, blocking=False)

    # 2. Configure FFmpeg pipe to push straight to MediaMTX
    ffmpeg_cmd = [
        'ffmpeg',
        '-probesize', '2M',
        '-analyzeduration', '2M',
        '-f', 'h264',             
        '-i', 'pipe:0', 
        '-c:v', 'copy',             
        '-f', 'rtsp', 
        '-rtsp_transport', 'tcp', 
        'rtsp://localhost:8554/oak'
    ]

    print("Initializing OAK-D Lite 1080p NV12 stream on DepthAI v3...")
    pipeline.start()

    # Start the FFmpeg subprocess
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    try:
        while pipeline.isRunning():
            # Wait and grab encoded H264 packets
            h264_packet = video_queue.get()
            if h264_packet is not None:
                # Push binary frame packets into the FFmpeg pipe loop
                proc.stdin.write(h264_packet.getData())
            else:
                time.sleep(0.001)
    except KeyboardInterrupt:
        print("\nStopping stream...")
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()