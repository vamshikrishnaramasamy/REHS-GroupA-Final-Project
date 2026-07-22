from app import create_app


app = create_app()


if __name__ == "__main__":
    # Port 5000 is taken by macOS's AirPlay Receiver, so this uses 5001 instead.
    # Binding 0.0.0.0 makes it reachable from other devices (e.g. an iPhone) on the LAN.
    app.run(host="0.0.0.0", port=5001, debug=True)
