/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;
const bit<8> TYPE_HULA = 0x90;
const bit<8> TYPE_ICMP = 0x01;
const bit<8> TYPE_TCP = 0x06;
const bit<8> TYPE_UDP = 0x11; 

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;
typedef bit<9> port_id_t;
typedef bit<8> util_t;
typedef bit<24> tor_id_t; 
typedef bit<48> time_t;

const time_t FLOWLET_THRESH = 48w1 << 3;
const util_t PROBE_FREQ_FACTOR = 6;
const time_t KEEP_ALIVE_THRESH = 48w1 << PROBE_FREQ_FACTOR;
const time_t FLOWLET_THRES = 48w1 << 3;
const int MAX_HOPS = 10; 
const bit<5> IPV4_OPTION_MRI = 31;

const port_id_t MAX_PORT_NUM = 255;
const tor_id_t MAX_TOR_NUM = 255;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;
}

header hula_t {
    bit<24> tor_id;
    bit<8>  path_util;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<8>    diffserv;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcAddr;
    ip4Addr_t dstAddr;
}

header ipv4_option_t{
    bit<1> copyFlag;
    bit<2> optClass;
    bit<5> option;
    bit<8> optionLength;
}

header mri_t {
    bit<16> count;
}

header switch_t{
    bit<32> swid; 
}

header tcp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<32> seq;
    bit<32> ack;
    bit<4> dataofs;
    bit<3> reserved;
    bit<9> flags;
    bit<32> window;
    bit<16> chksum;
    bit<16> urgptr;
}

struct metadata {
    bit<16> remaining;
    bit<8> next_hop;
    bit<32> dst_tor;
}

struct headers {
    ethernet_t              ethernet;
    ipv4_t                  ipv4;
    ipv4_option_t           ipv4_option;
    mri_t                   mri;
    switch_t[MAX_HOPS]      swtraces;
    hula_t                  hula;
    tcp_t                   tcp;
}

parser HulaParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }
    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4 : parse_ipv4;
            default   : accept;
        }
    }
    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.ihl) {
            5: parse_ipv4_protocol;
            default: parse_ipv4_option;
        }
    }
    state parse_ipv4_option {
       packet.extract(hdr.ipv4_option);
       transition select(hdr.ipv4_option.option){
           IPV4_OPTION_MRI: parse_mri;
           default: accept;
       }
    }
    state parse_mri {
        packet.extract(hdr.mri);
        meta.remaining = hdr.mri.count; 
        transition select (meta.remaining) {
            0 : parse_ipv4_protocol;
            default: parse_swtrace;
        }
    }
    state parse_swtrace {
        packet.extract(hdr.swtraces.next);
        meta.remaining = meta.remaining  - 1;
        transition select(meta.remaining) {
            0 : parse_ipv4_protocol;
            default: parse_swtrace;
        }
    }
    state parse_ipv4_protocol {
        transition select(hdr.ipv4.protocol){
            TYPE_HULA: parse_hula;
            TYPE_TCP: parse_tcp;
            default: accept;
        }
    }
    state parse_hula {
        packet.extract(hdr.hula);
        transition accept;
    }

    state parse_tcp {
        packet.extract(hdr.tcp);
        transition accept;
    } 
}

control HulaVerifyChecksum(inout headers hdr, inout metadata meta) {   
    apply {  }
}

control HulaIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {
    register<bit<32>>(1) switch_tor_id;
    /* port_number -> port utilization*/
    register<util_t>((bit<32>)MAX_PORT_NUM) port_util;
    /* port_number -> updated time of port_utilization */ 
    register<time_t>((bit<32>) MAX_PORT_NUM) port_util_updated_time;
    /*gives the utilization of the best path from the switch to a destination TOR */ 
    register<util_t>((bit<32>) MAX_TOR_NUM) min_path_util;
    /*gives the net hop that has the minimum path utilization for the ToR in the path util table */
    register<port_id_t>((bit<32>) MAX_TOR_NUM) best_hop;
    /* dst_tor_id -> timestamp of a update of its entry'*/
    register<time_t>((bit<32>)MAX_TOR_NUM) update_time;
    /* dst_tor_id -> timestamp in flowlet table */
    register<time_t>((bit<32>)1021) flowlet_timestamp;
    /* dst_tor_id -> next_hop in flowlet table */ 
    register<port_id_t>((bit<32>)1021) flowlet_next_hop;
    
    action hula_logic(){
        port_id_t ingress_port = (bit<9>)standard_metadata.ingress_port;

        /* read putilization from ingress_port, if port_util is */
	util_t tx_util;
	port_util.read(tx_util, (bit<32>)ingress_port);
	if (hdr.hula.path_util < tx_util) {
            hdr.hula.path_util = tx_util;
        }

        util_t min_util;
        min_path_util.read(min_util, (bit<32>)hdr.hula.tor_id);    
        
        time_t curr_time = standard_metadata.ingress_global_timestamp;
        time_t uptime;
        update_time.read(uptime, (bit<32>)hdr.hula.tor_id);

        /* condition to update the table */
        bool cond = (min_util > hdr.hula.path_util) || (curr_time - uptime > KEEP_ALIVE_THRESH);
	
	/* update utilization on corresponding dst_tor */ 
	util_t temp_util;
        temp_util = cond ? hdr.hula.path_util : min_util;
	min_path_util.write((bit<32>)hdr.hula.tor_id, temp_util);

        /* update best_hop on corresponding dst_tor */
        port_id_t temp_port; 
        best_hop.read(temp_port, (bit<32>)hdr.hula.tor_id);
        temp_port = cond ? standard_metadata.ingress_port : temp_port;
        best_hop.write((bit<32>)hdr.hula.tor_id, temp_port);
       	 
        /* update updated_time */
        time_t temp_time;
        temp_time = cond ? curr_time : uptime;
    	update_time.write((bit<32>)hdr.hula.tor_id, temp_time); 
	
        util_t hula_util;
        min_path_util.read(hula_util , (bit<32>)hdr.hula.tor_id);
        hdr.hula.path_util = hula_util;
    }

    action eval_util() {
        util_t utilization;
        time_t last_update;

        time_t cur_time = standard_metadata.ingress_global_timestamp;
        bit<32> ingress_port= (bit<32>) standard_metadata.ingress_port;

        port_util.read(utilization, ingress_port); 
        port_util_updated_time.read(last_update, ingress_port);

        bit<8> delta_t = (bit<8>) (cur_time - last_update);
        utilization = (((bit<8>) standard_metadata.packet_length + utilization) << PROBE_FREQ_FACTOR) - delta_t;
        utilization = utilization >> PROBE_FREQ_FACTOR;
        /* update utilization of port */
        port_util.write(ingress_port, utilization);
        port_util_updated_time.write(ingress_port, cur_time);
    }

    action send_to_host(){
        time_t cur_time = standard_metadata.ingress_global_timestamp;
        bit<32> dst_tor = (bit<32>) hdr.hula.tor_id;

        util_t ingress_port_util;
        port_util.read(ingress_port_util, (bit<32>) standard_metadata.ingress_port); 

        bit<32> flow_hash; 
        time_t flow_time; 
        port_id_t flow_hop; 
        port_id_t bhop;

        hash(flow_hash, HashAlgorithm.csum16, 32w0, {
            hdr.ipv4.srcAddr,
            hdr.ipv4.dstAddr,
            hdr.ipv4.protocol,
            hdr.tcp.srcPort,
            hdr.tcp.dstPort 
        }, 32w1 << 9 - 1); 
        
        /* based from the hash read from flowlet_time*/ 
        flowlet_timestamp.read(flow_time, flow_hash); 
	bool cond = (cur_time - flow_time > FLOWLET_THRES);
        /* if flowlet time is over the threshold */
	port_id_t tmp;
	flowlet_next_hop.read(tmp, flow_hash);
        best_hop.read(bhop, meta.dst_tor);
	tmp = cond ? bhop : tmp;
        flowlet_next_hop.write(flow_hash, tmp);
         
        flowlet_next_hop.read(flow_hop, flow_hash);
        standard_metadata.egress_spec = flow_hop;
        flowlet_timestamp.write(flow_hash, cur_time);
    }
	
    action drop() {
        mark_to_drop(standard_metadata);
    }

    action set_dst_tor(){
        if (hdr.hula.isValid()){
            meta.dst_tor = (bit<32>)hdr.hula.tor_id;
        } else if (hdr.tcp.isValid() && hdr.ipv4.isValid()){
            meta.dst_tor = (hdr.ipv4.dstAddr & 0x0000ff00) >> 8;
        }
    }

    action simple_forward(egressSpec_t port) {
        standard_metadata.egress_spec = port;
    }

    table edge_forward {
        key = {
          hdr.ipv4.dstAddr: exact;
        }
        actions = {
          simple_forward;
          NoAction;
        }
        default_action = NoAction;
    }
    
    table hula_tbl {
        key = {
            hdr.ipv4.protocol: exact;
        }
        actions = {
	    hula_logic;
            drop;
        }
        size = 4;
        default_action = drop(); 
    }
    
    action h_mcast(){ 
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
        standard_metadata.mcast_grp = (bit<16>)standard_metadata.ingress_port;
    }

    table hula_mcast {
        key = {
            hdr.ipv4.dstAddr: exact;
        }
        actions = {
            h_mcast;
            drop;
        }
        default_action = drop();
    }

    apply {
        set_dst_tor();
        if (hdr.ipv4.isValid() && hdr.ipv4.ttl > 0) {
            if(hdr.hula.isValid()) {
                bit<32> tor_num;
                switch_tor_id.read(tor_num, 0);
                if (meta.dst_tor == tor_num) {
                    drop();
                    return; 
                }
                eval_util();
                hula_tbl.apply();
                hula_mcast.apply();
                return;
            }
            bit<32> tor_num;
            switch_tor_id.read(tor_num, 0);
            if (meta.dst_tor == tor_num) {
                edge_forward.apply();
            }else {
                send_to_host();
            }
        } else {drop();}
    }
}

control HulaEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    action drop(){
        mark_to_drop(standard_metadata);
    }

    action add_swtrace(bit<32> swid) {
        hdr.mri.count = hdr.mri.count + 1;
        hdr.swtraces.push_front(1);
        hdr.swtraces[0].setValid();
        hdr.swtraces[0].swid = swid;

        hdr.ipv4.ihl = hdr.ipv4.ihl + 1;
        hdr.ipv4_option.optionLength = hdr.ipv4_option.optionLength + 4;
        hdr.ipv4.totalLen = hdr.ipv4.totalLen + 4;
    }

    table swtrace {
        actions = {
            add_swtrace;
            NoAction;
        }
        default_action = NoAction();
    }
   
    apply {
	if(standard_metadata.egress_port == standard_metadata.ingress_port) drop();
        if(hdr.mri.isValid()) {
            swtrace.apply(); 
        }
    }
}

control HulaComputeChecksum(inout headers hdr, inout metadata meta) {
     apply {
	update_checksum(
	    hdr.ipv4.isValid(),
            { hdr.ipv4.version,
	      hdr.ipv4.ihl,
              hdr.ipv4.diffserv,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcAddr,
              hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

control HulaDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.ipv4_option);
      	packet.emit(hdr.mri);
        packet.emit(hdr.swtraces);
        packet.emit(hdr.hula);
        packet.emit(hdr.tcp);
    }
}

V1Switch(
HulaParser(),
HulaVerifyChecksum(),
HulaIngress(),
HulaEgress(),
HulaComputeChecksum(),
HulaDeparser()
) main;
