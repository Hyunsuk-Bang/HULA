.PHONY: run 

include  ../hangar.mk

TARGET_FILES=$(BLD_BMV2)/networks/hula/hula.json
CORE_SWITCHES=4
GROUPS=4
AGG_SWITCHES=2
HOSTS=2

run:
	HANGARGAMES=$(HANGAR) TOPOLOGY=$(HANGAR)/networks/hula/hula.yml ./run_hula.sh

hula_top_gen: 
	sudo python3 ./topology_gen.py -c $(CORE_SWITCHES) -g $(GROUPS) -a $(AGG_SWITCHES) -host $(HOSTS)

hula_clean:
	sudo rm -rf *.cmd
	sudo rm -rf *.yml
	sudo rm -rf *.gif
	sudo rm -rf ./hula_images
	sudo mkdir ./hula_images
	sudo rm -rf ./hangargames_output

hula_make_gif:
	rm -rf ./hula_images/network_topology.gv.png
	sudo python3 ./pngs_to_gif.py

hula_link_failure:
	sudo ip link set dev c0-eth1 down
	sudo ip link set dev c1-eth2 down
	sudo ip link set dev c2-eth3 down
	sudo ip link set dev c3-eth4 down

hula_link_recover: 
	sudo ip link set dev c3-eth1 up 
	sudo ip link set dev c3-eth2 up 
	sudo ip link set dev c3-eth3 up 
	sudo ip link set dev c3-eth4 up 
	sudo ip link set dev c2-eth1 up 
	sudo ip link set dev c2-eth2 up 
	sudo ip link set dev c2-eth3 up 
	sudo ip link set dev c2-eth4 up 
	sudo ip link set dev c1-eth1 up 
	sudo ip link set dev c1-eth2 up 
	sudo ip link set dev c1-eth3 up 
	sudo ip link set dev c1-eth4 up 
	sudo ip link set dev c0-eth1 up 
	sudo ip link set dev c0-eth2 up 
	sudo ip link set dev c0-eth3 up 
	sudo ip link set dev c0-eth4 up 
