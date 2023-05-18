#!usr/bin/python3
import argparse
import networkx as nx
import ruamel.yaml
import random
import socket
from ruamel.yaml.scalarstring import (DoubleQuotedScalarString as dq,   
                                      SingleQuotedScalarString as sq)
from graphviz import Digraph

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--core_switch_num')
parser.add_argument('-g', '--group_num')
parser.add_argument('-a', '--agg_per_group')
parser.add_argument('-host', '--hosts_per_leaf')
args = parser.parse_args()

number_of_core_switch = int(args.core_switch_num) 
number_of_group = int(args.group_num) 
number_of_agg_per_group = number_of_leaf_per_group = int(args.agg_per_group) 
number_of_hosts_per_leaf = int(args.hosts_per_leaf) 
cfg = "../../build/BMv2/networks/hula/hula.json"
macs_in_use = set()

# from generate_alv_network.py by Professor Nik Sultana
def generate_mac_address():
    while True:
        candidate = "02:00:00:%02x:%02x:%02x" % (random.randint(0, 255),
                             random.randint(0, 255),
                             random.randint(0, 255))
        if candidate not in macs_in_use:
            macs_in_use.add(candidate)
            break
    return candidate

# from generate_alv_network.py by Professor Nik Sultana
class IPv4Address:
    def __init__(self, o1, o2, o3, o4, subnet):
        self.o1 = o1
        self.o2 = o2
        self.o3 = o3
        self.o4 = o4
        self.subnet = subnet
    def toString(self):
        return str(self.o1) + "." + str(self.o2) + "." + str(self.o3) + "." + str(self.o4) + "/" + str(self.subnet) 

def generate_fat_tree():
    G = nx.Graph()
    # Create the core switches
    for c in range(number_of_core_switch):
        G.add_node('c{}'.format(c), interfaces = [], programs = [], cmds = [])

    # Create the aggregation switches
    for g in range (number_of_group): 
        for a in range(number_of_agg_per_group):
            G.add_node('a{}_{}'.format(g, a), interfaces = [], programs = [], cmds = [])
            for l in range(number_of_leaf_per_group):
                G.add_node('l{}_{}'.format(g, l), interfaces = [], programs = [], cmds = [])
                G.add_edge('a{}_{}'.format(g,a), 'l{}_{}'.format(g, l))

    # Create the edge switches and hosts
    for g in range(number_of_group):
        for l in range(number_of_leaf_per_group):
            for h in range(number_of_hosts_per_leaf):
                G.add_node('h{}_{}_{}'.format(g,l,h), interfaces = [], programs = [])
                G.add_edge('l{}_{}'.format(g, l), 'h{}_{}_{}'.format(g,l,h))

    # Connect the aggregation switches to the core switches
    for i in range(number_of_core_switch):
        for g in range(number_of_group):
            for a in range(number_of_agg_per_group // 2):
                if i < number_of_core_switch // 2:
                    G.add_edge('c{}'.format(i), 'a{}_{}'.format(g, a))
                else:
                    G.add_edge('c{}'.format(i), 'a{}_{}'.format(g, a + 1))

    return G

def gen_switch_id(switch):
    switch_type = switch[0]
    if switch_type == 'l':
        switch_grp = int(switch[1:].split("_")[0])
        switch_num = int(switch[1:].split("_")[1])
        switch_id = switch_grp * (number_of_agg_per_group * number_of_leaf_per_group) + switch_num
        return switch_id

    if switch_type == 'a':
        switch_grp = int(switch[1:].split("_")[0])
        switch_num = int(switch[1:].split("_")[1])
        switch_id = switch_grp * (number_of_agg_per_group * number_of_leaf_per_group) + switch_num + number_of_leaf_per_group
        return switch_id

    if switch_type == 'c':
        switch_num = int(switch[1:])
        switch_id = number_of_group * number_of_agg_per_group * number_of_leaf_per_group + switch_num
        return switch_id

def config_interfaces (G): 
    hosts = []
    switches = []
    hosts_ipv4_addr = []
    for node in G.nodes():
        # populating host info
        if node[0] == 'h':
            hosts.append(node)
            node_info = node[1:].split('_')
            mac = generate_mac_address()
            g = int(node_info[0])
            l = int(node_info[1])
            h = int(node_info[2])
            ipv4 = IPv4Address(10, 0, g * number_of_leaf_per_group + l, h + 2, 24) 
            hosts_ipv4_addr.append(ipv4) 
            G.nodes[node]['interfaces'].append(
                {
                    'mac': sq(mac),
                    'ip': ipv4.toString(),
                    'port': 1
                }
            )
            G.nodes[node]['programs'].append(
                {
                    'cmd': dq("echo 'Hello from' " + node), 
                    'fg': True
                }
            ) 
            G.nodes[node]['programs'].append(
                {
                    'cmd': dq("sudo arp -v -i " + node + "-eth1 -s " + ipv4.toString().split("/")[0] + " " + mac), 
                    'fg': True
                }
            ) 
            G.nodes[node]['programs'].append(
                {
                    'cmd': dq("sudo route add default " + node + "-eth1"),
                    'fg': True
                }
            ) 
            continue

        else:
            switches.append(node)
            port_num = 1
            for (pred_node, succ_node) in G.edges():  
                if pred_node != node and succ_node != node:
                    continue

                G.nodes[node]['interfaces'].append(
                    {
                        'link': pred_node if pred_node != node else succ_node,
                        'mac': sq(generate_mac_address()),
                        'port': port_num
                    } 
                )
                port_num = port_num + 1 

    # add hosts cmds 
    for host in hosts:
        for h in hosts:
            G.nodes[host]['programs'].append(
                {
                    'cmd': dq('sudo arp -v -i ' + host + "-eth1 -s " + G.nodes[h]['interfaces'][0]['ip'].split("/")[0] + " " + G.nodes[h]['interfaces'][0]['mac'])
                }
            )

    base_thrift = 9090
    switches.sort()
    # add switches cmds
    for switch in switches:
        G.nodes[switch]['cmds'].append(
            "table_add hula_tbl hula_logic 0x90 =>"
        ) 
        G.nodes[switch]['cmds'].append(
            "table_add hula_mcast h_mcast 224.0.0.1 =>"
        )
        G.nodes[switch]['cmds'].append(
            "table_add swtrace add_swtrace => {}".format(gen_switch_id(switch))
        )

        if switch[0] == "l": 
            G.nodes[switch]['programs'] = [dq("simple_switch_CLI --thrift-port {} < ./{}.cmd".format(base_thrift, switch))]
            g = int(switch[1:].split("_")[0])
            l = int(switch[1:].split("_")[1])
            #add port rule from leaf -> host
            for i in range(number_of_hosts_per_leaf):
                host_ipv4 = IPv4Address(10, 0, g * number_of_leaf_per_group + l, 2+i, 24)
                G.nodes[switch]['cmds'].append(
                    "table_add edge_forward simple_forward " + host_ipv4.toString().split("/")[0] + " => " + str(i+3)
                )
            G.nodes[switch]['programs'].append(dq("chmod u+x generate_probe.py"))
            G.nodes[switch]['programs'].append(dq("sudo python3 ./generate_probe.py -i {} -d {}".format(switch, str(g*number_of_leaf_per_group+l)) )) 
            with open(switch + ".cmd", "w") as file:
                file.write("register_write switch_tor_id 0 {}".format(g * number_of_leaf_per_group + l))     
        elif switch[0] == "a":
            G.nodes[switch]['programs'] = [dq("simple_switch_CLI --thrift-port {} < ./a.cmd".format(base_thrift))]
        else:
            G.nodes[switch]['programs'] = [dq("simple_switch_CLI --thrift-port {} < ./c.cmd".format(base_thrift))]

        base_thrift += 1 

    return G, hosts, switches


def generate_yaml(G, hosts, switches):
    host_cfg = {}
    switch_cfg = {}
    hosts.sort()
    switches.sort()
    for host in hosts:
        h = {
            'interfaces': G.nodes[host]['interfaces'],
            'programs': G.nodes[host]['programs']     
        }        
        host_cfg[host] = h
    for switch in switches: 
        s = {}
        s['cfg'] = cfg
        s['interfaces'] = G.nodes[switch]['interfaces']
        s['cmds'] = G.nodes[switch]['cmds']
        s['programs'] = G.nodes[switch]['programs']
        switch_cfg[switch] = s
    # Generate the YAML file
    data = {
        'hosts': host_cfg,
        'switches': switch_cfg
    }
    with open('hula.yml', 'w') as file:
        yaml = ruamel.yaml.YAML()
        yaml.dump(data, file)

def generate_agg_swtich_cmd(G, agg_switch): 
    links = G.nodes[agg_switch]['interfaces']
    uplink_filter = lambda x : x['link'][0] == 'c'
    uplinks = list(filter(uplink_filter, links))
    downlink_filter = lambda x : x['link'][0] == 'l'
    downlinks = list(filter(downlink_filter, links)) 
    downlinks_port = list(map(lambda d : d['port'], downlinks))
    downlinks_port = list(map(str, downlinks_port))
    all_ports = list(map(lambda d : d['port'], links))
    mgrp_num = 1 
    with open('a.cmd', 'w') as file:
        for uplink in uplinks:
            file.write("mc_node_create {} {}\n".format(uplink["port"], " ".join(downlinks_port)))
            file.write("mc_mgrp_create {}\n".format(mgrp_num))
            file.write("mc_node_associate {} {}\n\n".format(mgrp_num, mgrp_num - 1))
            mgrp_num += 1 

        for downlink in downlinks:
            from_port = downlink['port']
            ports = list(filter(lambda d : d != from_port, all_ports))
            ports = list(map(str, ports))
            file.write("mc_node_create {} {}\n".format(downlink["port"], " ".join(ports)))
            file.write("mc_mgrp_create {}\n".format(mgrp_num))
            file.write("mc_node_associate {} {}\n\n".format(mgrp_num, mgrp_num - 1))
            mgrp_num += 1 

        file.write("register_write switch_tor_id 0 -1")

def generate_core_switch_cmd(G, core_switch):
    links = G.nodes[core_switch]['interfaces']
    all_ports = list(map(lambda d : d['port'], links))
    mgrp_num = 1 
    with open('c.cmd', 'w') as file:
        for link in links:
            from_port = link['port']
            ports = list(filter(lambda d : d != from_port, all_ports))
            ports = list(map(str, ports))
            file.write("mc_node_create {} {}\n".format(link["port"], " ".join(ports)))
            file.write("mc_mgrp_create {}\n".format(mgrp_num))
            file.write("mc_node_associate {} {}\n\n".format(mgrp_num, mgrp_num - 1))
            mgrp_num += 1
        
        file.write("register_write switch_tor_id 0 -1") 


def generate_topology_png(G, hosts, switches):
    g = Digraph('network_topology')
    core = Digraph('core')
    agg = Digraph('agg')
    leaf = Digraph('leaf')
    host_nodes = Digraph('host')
    leaf_switches = []
    core_switches = []
    agg_switches = []
    core.attr(rank='min')
    agg.attr(rank='same')
    leaf.attr(rank='same')
    host_nodes.attr(rank='max')
    for host in hosts: 
        host_nodes.node(host)
    for i in range(len(hosts)-1):
        host_nodes.edge(hosts[i], hosts[i+1], dir='none', style='invis')

    for switch in switches:
        if switch[0] == 'l':
            leaf_switches.append(switch)
            leaf.node(switch)
        elif switch[0] == 'a':
            agg_switches.append(switch)
            agg.node(switch)
        else:
            core_switches.append(switch)
            core.node(switch)
    for i in range(len(leaf_switches) - 1):
        leaf.edge(leaf_switches[i], leaf_switches[i+1] , dir='none', style='invis')
    for i in range(len(agg_switches) - 1):
        agg.edge(agg_switches[i], agg_switches[i+1] , dir='none', style='invis')
    for i in range(len(core_switches) - 1):
        core.edge(core_switches[i], core_switches[i+1] , dir='none', style='invis')

    g.subgraph(core)
    g.subgraph(agg)
    g.subgraph(leaf)
    g.subgraph(host_nodes)

    edge_set = set()
    for switch in switches:
        ifs = G.nodes[switch]['interfaces']
        for iface in ifs:
            link = iface['link']
            if (switch, link) not in edge_set or (link, switch) not in edge_set:
                g.edge(switch, link, dir='none')
                edge_set.add((switch, link))
                edge_set.add((link, switch))

    with open('./hula_images/hula.dot', 'w') as f:
        f.write(g.source)
    g.render(format='png', directory='./hula_images/')


G = generate_fat_tree()
G, hosts, switches = config_interfaces(G)
generate_yaml(G, hosts, switches)
generate_agg_swtich_cmd(G, 'a0_0')
generate_core_switch_cmd(G, 'c0')
generate_topology_png(G, hosts, switches)
