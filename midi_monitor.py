import mido

# Replace this with your exact loopMIDI port name (e.g., 'Clock 1')
PORT_NAME = 'Clock 0'

print(f"Listening for MIDI messages on '{PORT_NAME}'...")
print("Press Ctrl+C to stop.")

try:
    # Open the port as an INPUT this time
    with mido.open_input(PORT_NAME) as inport:
        for msg in inport:
            print(msg)
except OSError:
    print(f"Error: Could not find port '{PORT_NAME}'. Is loopMIDI running?")