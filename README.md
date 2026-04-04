# NoiseSniffer

You can visualize network activity with a packet sniffer like WireShark...
But what if you could HEAR the network? This accomodates those with visual impairment.

By James Horan and Oliver Tasset

---

NoiseSniffer sniffs packets on a network, and uses the packet stream to create customized noise. Each type of packet can have its own unique frequency boost, and also unique sound set by the user (wind, forest, fire, white noise). You can add loud beeps or loud horns for suspicious or malicious packets. The noise should "Sound like the network".

In the case of a SYN flood or DoS attack, the sheer amount of packets will boost the sound into distortion territory, sounding harsh and load.

## Display
We will display three tabs that you can switch between.

Tab 1:
Show the incoming packet stream like wireshark

Tab 2:
Show a spectrum analyzer for activity. You should see little lines for which frequency boost is which port number, and then drag it around like an EQ visualizer. (This might be a stretch goal).

Tab 3:
You can create basic rules for port number with whitelisted IPs just like a firewall
Instead of blocking/allowing a connection, you assign a sound and frequency (boost).

In the case of a SYN flood or DoS attack, the sheer amount of packets will boost the sound into distortion territory, sounding harsh and load.

Crazy stretch goal: UI is fully accessible for the blind. Voice activated rules.

## Tech stack:

Python (backend)
Scapy (for parsing network packets)
SoundDevice (Generate noise + apply filters in real time)
NumPy (signal processing)
SciPy (filters)
React (front-end)
FastAPI (WebSocket support)

