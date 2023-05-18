mc_node_create 1 2 3 4
mc_mgrp_create 1
mc_node_associate 1 0

mc_node_create 2 1 3 4
mc_mgrp_create 2
mc_node_associate 2 1

mc_node_create 3 1 2 4
mc_mgrp_create 3
mc_node_associate 3 2

mc_node_create 4 1 2 3
mc_mgrp_create 4
mc_node_associate 4 3

register_write switch_tor_id 0 -1