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
    h1.cmd("cd ~/Desktop/lib")
    h1.cmdPrint("ps")
    h1.cmdPrint("python3 -m http.server 8080 &")
    h1.cmdPrint("ps")
    h1.cmdPrint("netstat -lp")

    h2.cmd("mkdir -p /tmp/mininet")
    h2.cmd("cd /tmp/mininet")
    h2.cmdPrint("wget -r http://10.0.0.1:8080")

    # CLI(net)
    net.pingAll()
    net.iperf()
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()

