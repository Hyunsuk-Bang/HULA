#!/usr/bin/env python3
import sys
import argparse

from scapy.all import (
    IP,
    FieldLenField,
    IntField,
    IPOption,
    Packet,
    PacketListField,
    ShortField,
    get_if_list,
    sniff
)
from scapy.layers.inet import _IPOption_HDR
import pydot

number_of_group = 4 
number_of_agg_per_group = number_of_leaf_per_group = 2 
graph = pydot.graph_from_dot_file('./hula_images/hula.dot')
idx = 0

class SwitchTrace(Packet):
    fields_desc = [ IntField("swid", 0)]
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

def host_ip_to_host(ip_addr): 
   x = int(ip_addr.split('.')[2])
   y = int(ip_addr.split('.')[3])
   grp = x // number_of_leaf_per_group
   leaf = x % number_of_leaf_per_group
   return 'h{}_{}_{}'.format(grp, leaf, y-2) 

def switch_id_to_switch(switch_id):
    x = number_of_agg_per_group * number_of_leaf_per_group
    if switch_id >= (number_of_group * number_of_agg_per_group * number_of_leaf_per_group):
        return 'c{}'.format(switch_id - x * number_of_group)
    elif (switch_id % x) < number_of_agg_per_group:
        return 'l{}_{}'.format(switch_id // x, switch_id % x)
    else:
        return 'a{}_{}'.format(switch_id // x, switch_id % x - number_of_leaf_per_group) 

def draw_graph(traces):
    graph = pydot.graph_from_dot_file('./hula_images/hula.dot')
    graph= graph[0]
    edges = graph.get_edges()
    for i in range(len(traces) - 1):
        n1 = traces[i]
        n2 = traces[i + 1]
        for edge in edges:
            src = edge.get_source()
            dst = edge.get_destination()
            if (src == n1 and dst == n2) or (src == n2 and dst == n1):  
                graph.del_edge(src, dst)
                new_edge = pydot.Edge(src, dst, dir='none', color = 'red')
                graph.add_edge(new_edge)
        graph.write_png('./hula_images/hula{:02d}.png'.format(idx))

def handle_pkt(pkt):
    global idx
    print("got a packet")
    pkt.show2()
    traces = []
    for swtraces in pkt[IPOption_MRI].swtraces:
       traces.append(swtraces.swid) 
    traces = list(map(switch_id_to_switch, traces))
    traces = [host_ip_to_host(pkt[IP].dst)] + traces + [host_ip_to_host(pkt[IP].src)]
    draw_graph(traces)
    idx += 1
    sys.stdout.flush()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', "--interface")
    args = parser.parse_args()
    iface = args.interface + '-eth1'
    print("sniffing on %s" % iface)
    sys.stdout.flush()
    sniff(filter="tcp and port 1", iface = iface,
          prn = lambda x: handle_pkt(x))

if __name__ == '__main__':
    main()
