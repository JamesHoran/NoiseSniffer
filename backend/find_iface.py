from scapy.all import get_if_list, sniff

for iface in get_if_list():
    print(f"\n--- {iface} ---")
    pkts = sniff(iface=iface, count=3, timeout=2)
    for p in pkts:
        print(p.summary())
