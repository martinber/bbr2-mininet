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

class MiHost(Host):
    """
    Host con algunas funciones mas.

    Hay varias funciones para correr comandos. Ademas de las defidas en esta
    clase, usamos:

    - self.cmd(): Correr un comando comun y esperar a que termine.

    - self.cmdPrint(): Correr un comando mostrando la salida y esperar a que
      termine.
    """

    def __init__(self, *args, **kwargs):
        super(MiHost, self).__init__(*args, **kwargs)

    def config(self, **params):
        super(MiHost, self).config(**params)

    def bgCmd(self, *cmd):
        """
        Corre un comando en el fondo y devuelve su PID.
        """
        cmd = cmd + ("&",)
        print(self.cmd(*cmd))
        return int(self.cmd("echo $!"))

    def killPid(self, pid):
        """
        Mata un proceso dado su PID.
        """
        self.cmd("kill", pid)

def parse_captcp_stat(text):

    def group(iterator, count):
        itr = iter(iterator)
        while True:
            yield tuple([itr.next() for i in range(count)])


    flow = ("0.1", 0)

    for lines in group(iter(text.splitlines()), 3):
        flow1 = lines[0].strip().split()[1]
        flow2 = lines[1].strip().split()[1]
        print(lines[2].strip().split())
        data1 = int(lines[2].strip().split()[3])
        data2 = int(lines[2].strip().split()[8])

        if data1 > flow[1]:
            flow = (flow1, data1)
        if data2 > flow[1]:
            flow = (flow2, data2)

    return flow[0]

def myNetwork():

    net = Mininet( topo=None,
                   build=False,
                   ipBase='10.0.0.0/8')

    info( '*** Iniciando\n')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch, failMode='standalone')

    h1 = net.addHost('h1', cls=MiHost, ip='10.0.0.1', defaultRoute=None)
    h2 = net.addHost('h2', cls=MiHost, ip='10.0.0.2', defaultRoute=None)

    net.addLink(h1, s1)
    net.addLink(h2, s1)

    #net.addLink( host, switch, bw=10, delay='5ms', loss=2, max_queue_size=1000, use_htb=True )

    net.build()

    for controller in net.controllers:
        controller.start()

    net.get('s1').start([])

    info( '*** Realizar pruebas\n')

    # --------------------------------------------------------------------------
    # Inicializar

    h1.cmd("modprobe tcp_bbr")
    h2.cmd("modprobe tcp_bbr")

    # --------------------------------------------------------------------------
    # Crear carpetas temporales y moverse ahi

    h1.cmd("rm -r /var/tmp/mininet")
    h1.cmd("mkdir -p /var/tmp/mininet/h1")
    h1.cmd("cd /var/tmp/mininet/h1")

    h2.cmd("mkdir -p /var/tmp/mininet/h2")
    h2.cmd("cd /var/tmp/mininet/h2")

    h1.cmd("mkdir -p ~/resultados/")

    # --------------------------------------------------------------------------
    # Servidor HTTP

    # pushd hace cd a una carpeta. Lo que tiene de bueno es que cuando use popd
    # puedo volver a la carpeta anterior
    h1.cmd("pushd /etc/apt/")
    h1.cmdPrint("ls")

    pid_py3 = h1.bgCmd("python3 -m http.server 8080")
    time.sleep(1)

    h2.cmdPrint("ls")
    h2.cmdPrint("wget -r http://10.0.0.1:8080")
    h2.cmdPrint("ls")

    h1.killPid(pid_py3)
    h1.cmd("popd")

    # --------------------------------------------------------------------------
    # Iperf3
    # Cliente manda a servidor

    pid_iperf = h2.bgCmd("iperf -s")
    time.sleep(1)

    pid_tcpdump = h1.cmdPrint("ip a")
    pid_tcpdump = h1.bgCmd("tcpdump -i h1-eth0 -w ./trace.pcap")
    h1.cmdPrint("iperf -c 10.0.0.2")

    h1.killPid(pid_tcpdump)
    h2.killPid(pid_iperf)

    h1.cmdPrint("pwd")
    h2.cmdPrint("pwd")

    salida = h1.cmd("captcp statistic ./trace.pcap | grep -E 'Flow|Data application layer'")
    print(salida)
    print parse_captcp_stat(salida)


    # --------------------------------------------------------------------------
    # Ver que se hayan cerrado los procesos

    time.sleep(1)
    if h1.waiting:
        print "h1 no salio"
    if h2.waiting:
        print "h2 no salio"
    if not h1.waiting and not h2.waiting:
        print "Todo bien"

if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()
