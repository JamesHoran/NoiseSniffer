# NoiseSniffer

You can visualize network activity with a packet sniffer like WireShark...
But what if you could HEAR the network?

By James Horan and Oliver Tasset

---

NoiseSniffer sniffs packets on a network, and uses the packet stream to create customized noise. Each type of packet can have its own unique frequency boost, and also unique sound set by the user (wind, forest, fire, white noise). You can add loud beeps or loud horns for suspicious or malicious packets. The noise should "Sound like the network".

We will display the incoming packet stream like wireshark, but also show a spectrum analyzer for activity. You should see little lines for which frequency boost is which port number, and then drag it around like an EQ visualizer. (This might be a stretch goal).

You can create basic rules for port number with whitelisted IPs just like firewall

In the case of a SYN flood or DoS attack, the sheer amount of packets will boost the sound into distortion territory, sounding harsh and load.

## Tech stack:

Python (backend)
Scapy (for parsing network packets)
PyAudio (Generate noise + apply filters in real time)
NumPy (signal processing)
SciPy (filters)
React (front-end)
FastAPI (WebSocket support)

