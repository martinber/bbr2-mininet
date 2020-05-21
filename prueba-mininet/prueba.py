#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from subprocess import call

import time

def myNetwork():

    net = Mininet( topo=None,
                   build=False,
                   ipBase='10.0.0.0/8')

    info( '*** Add switches\n')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch, failMode='standalone')

    info( '*** Add hosts\n')
    h1 = net.addHost('h1', cls=Host, ip='10.0.0.1', defaultRoute=None)
    h2 = net.addHost('h2', cls=Host, ip='10.0.0.2', defaultRoute=None)

    info( '*** Add links\n')
    net.addLink(h1, s1)
    net.addLink(h2, s1)

    info( '*** Starting network\n')
    net.build()

    info( '*** Starting controllers\n')
    for controller in net.controllers:
        controller.start()

    info( '*** Starting switches\n')
    net.get('s1').start([])

    info( '*** Post configure switches and hosts\n')


    info( '*** Tests\n')
    h1.cmd("cd /etc/apt/")
    h1.cmdPrint("ls")

    h1.cmd("python3 -m http.server 8080 &")
    pid_python3 = int(h1.cmd("echo $!"))
    time.sleep(1)

    h2.cmd("rm -r /tmp/mininet")
    h2.cmd("mkdir -p /tmp/mininet")
    h2.cmd("cd /tmp/mininet")
    h2.cmdPrint("ls")
    h2.cmdPrint("wget -r http://10.0.0.1:8080")
    h2.cmdPrint("ls")

    h1.cmd("kill", pid_python3)

    time.sleep(1)
    if h1.waiting:
        print "h1 no salio"
    if h2.waiting:
        print "h2 no salio"

if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()

