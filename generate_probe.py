#!/usr/bin/python3
import argparse
import sys
import socket
import random
import struct
import time
import argparse

from scapy.all import sendp, send, get_if_list, get_if_hwaddr, bind_layers
from scapy.all import Packet, BitField, Raw
from scapy.all import Ether, IP

class Hula(Packet):
    fields_desc = [
        BitField("dst_tor", 0, 24),
        BitField("path_util", 0, 8)
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', "--interface")
    parser.add_argument('-d', "--dst_tor")
    args = parser.parse_args()
    dst_tor_num = int(args.dst_tor) 
    print(dst_tor_num)
    ifs = get_if_list()
    f = lambda x : args.interface in x
    g = lambda y : y == args.interface + "-eth1" or y == args.interface + "-eth2"
    ifs = list(filter(f, ifs))
    ifs = list(filter(g, ifs))

    bind_layers(IP, Hula, proto=144)
    
    while True:    
        for iface in ifs:
            hw_if = get_if_hwaddr(iface)
            pkt = Ether(src = hw_if, dst = "ff:ff:ff:ff:ff:ff")
            pkt = pkt / IP(dst = "224.0.0.1", proto = 144)
            pkt = pkt / Hula(dst_tor = dst_tor_num, path_util = 256)
            pkt = pkt / Raw("prb") 
            sendp(pkt, iface=iface, verbose=True)
        time.sleep(1)

if __name__ == '__main__':
    main()
