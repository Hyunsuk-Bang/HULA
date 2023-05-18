import argparse
import socket
import time

from scapy.all import *
from scapy.all import Ether, IP, TCP, IPOption
from scapy.layers.inet import _IPOption_HDR

def get_if():
    ifs=get_if_list()
    iface=None # "h1-eth0"
    for i in get_if_list():
        if "eth1" in i:
            iface=i
            break;
    if not iface:
        print("Cannot find eth0 interface")
        exit(1)
    return iface

class SwitchTrace(Packet):
    fields_desc = [IntField("swid", 0)]
    def extract_padding(self, p):
                return "", p

class IPOption_MRI(IPOption):
    name = "MRI"
    option = 31
    fields_desc = [ _IPOption_HDR,
                    FieldLenField("length", None, fmt="B",
                                  length_of="swtraces",
                                  adjust=lambda pkt,l:l*2+4),
                    ShortField("count", 0),
                    PacketListField("swtraces",
                                   [],
                                   SwitchTrace,
                                   count_from=lambda pkt:(pkt.count*1)) ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', "--interface")
    parser.add_argument('-d', "--dst_ip_addr")
    args = parser.parse_args()

    dst_ip_addr = args.dst_ip_addr
    
    iface = get_if()
    hw_if = get_if_hwaddr(iface)
    print(hw_if)

    for i in range(50):
        pkt = Ether(src=hw_if, dst = "ff:ff:ff:ff:ff:ff")
        pkt = pkt / IP(dst = args.dst_ip_addr, proto = 0x6, options = IPOption_MRI(count=0, swtraces=[]))
        pkt = pkt / TCP(dport = 1, seq=i) / "hula is cool"
        print("sending TCP packet to {}".format(dst_ip_addr))
        sendp(pkt, iface = iface)
        time.sleep(0.5)

if __name__ == '__main__': 
    main();
