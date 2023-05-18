### HULA LOAD BALANCER
Name: Hyunsuk Bang
<br>
Email: hbang3@hawk.iit.edu

This project is a replication of the paper <HULA : Scalable Load Balancing Using Programmable Data Planes> by N Katta. 
"https://conferences.sigcomm.org/sosr/2016/papers/sosr_paper67.pdf"

HULA is a Hop-by-Hop Utilization aware Load balancing architecture works on fat-tree topology.
HULA switches always choose the next best hop given the destination TOR switches. <br>
It can handle link assymetry and sudden link failure. <br>


## Install and Run HULA loadbalancer
0. pip3 install -r requirements.txt
1. make compile
2. sudo hula_top_gen (to change the number of core switches, aggregated switches, and leaf switches, edit environmnet variable in Makefile) <br>
3. sudo make run

## Visualize
To visualize the life of packet traveling from host A to host B - 
1. start by doing 'To start' section
2. generate each screen of host A and host B<br>
```
mininet> hostA create_screen A
mininet> hostB create_screen B
```
3. attach screen of host A and host B (make sure to do this in different shell session)<br>
``` 
$ sudo attach_screen A
$ sudo attach_screen B
```

4. send tcp packets from A to B<br>
 ``` 
  (sender) $ sudo python3 ./send.py -i [A's network interface] -d [B's IP address]
(receiver) $ sudo python3 ./receive.py -i [B's network interface]
  ```
This will generate image files under ./hula_images file showing which paths that a packet taken<br>

5. Generate GIF<br>
  ```
$ make hula_make_gif
  ```
The output will be hula.gif
                            ![hula](https://github.com/Hyunsuk-Bang/HULA/assets/84240134/2d4f0750-ad31-4fca-a2e2-daceec83c355)


##Test link asymmetry or link failure<br>
  ```
$ make hula_link_failure
  ```
link recover<br>
  ```
$ make hula_link_recover
  ```
 
 ## Test results (ALV vs HULA)
 https://docs.google.com/presentation/d/1OI1EZqZnLkBtFJu1vWRQZdUSB-iZnjZGZ7jF9nsa97U/edit?usp=sharing

