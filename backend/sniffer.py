from scapy.all import sniff, IP, TCP, UDP, ICMP
from datetime import datetime, timezone


def parse_packet(packet):
    if not packet.haslayer(IP):
        return None

    ip = packet[IP]
    timestamp = datetime.now(timezone.utc).isoformat()
    protocol = None
    src_port = None
    dst_port = None
    flags = None

    if packet.haslayer(TCP):
        tcp = packet[TCP]
        protocol = "TCP"
        src_port = tcp.sport
        dst_port = tcp.dport
        flags = str(tcp.flags)
    elif packet.haslayer(UDP):
        udp = packet[UDP]
        protocol = "UDP"
        src_port = udp.sport
        dst_port = udp.dport
    elif packet.haslayer(ICMP):
        protocol = "ICMP"
    else:
        protocol = str(ip.proto)

    return {
        "type": "packet",
        "timestamp": timestamp,
        "src_ip": ip.src,
        "dst_ip": ip.dst,
        "src_port": src_port,
        "dst_port": dst_port,
        "protocol": protocol,
        "flags": flags,
        "length": len(packet),
        "packet_type": "normal",
    }


LOG_FILE = "packets.log"


def handle_packet(packet):
    parsed = parse_packet(packet)
    if parsed:
        print(packet.summary())
        with open(LOG_FILE, "a") as f:
            f.write(str(parsed) + "\n")


IFACE = r"\Device\NPF_{D1E60D1D-DACE-48C1-9915-47A46F14DFF0}"

if __name__ == "__main__":
    timeout = 10
    print(f"Sniffing on {IFACE} for {timeout} seconds, logging to {LOG_FILE}...")
    sniff(iface=IFACE, filter="ip", prn=handle_packet, store=False, timeout=timeout)
    print("Done")
