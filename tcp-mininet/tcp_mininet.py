#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import CPULimitedHost, Host, Node
from mininet.node import OVSKernelSwitch, UserSwitch
from mininet.node import IVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink, Intf
from mininet.util import pmonitor
from subprocess import call

import parse

import time
import signal

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
        Manda Ctrl-C a un proceso dado su PID.
        """
        self.cmdPrint("kill -INT {}".format(pid))

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
    #h1.cmd("pushd /etc/apt/")
    #h1.cmdPrint("ls")

    #pid_py3 = h1.bgCmd("python3 -m http.server 8080")
    #time.sleep(1)

    #h2.cmdPrint("ls")
    #h2.cmdPrint("wget -r http://10.0.0.1:8080")
    #h2.cmdPrint("ls")

    #h1.killPid(pid_py3)
    #h1.cmd("popd")

    # --------------------------------------------------------------------------
    # Iperf3
    # Cliente manda a servidor

    pid_iperf = h2.bgCmd("iperf -s")
    time.sleep(1)

    pid_tcpdump = h1.bgCmd("tcpdump -i h1-eth0 -w ./trace.pcap")
    h1.cmd("mkdir ./captcp_ss")
    pid_captcp_ss = h1.bgCmd("captcp socketstatistic -s 10 -o ./captcp_ss") # 10Hz
    #popen_captcp_ss = h1.popen("captcp socketstatistic -s 10 -o ./captcp_ss &") # 10Hz
    #h1.sendCmd("captcp socketstatistic -s 10 -o ./captcp_ss &") # 10Hz
    #popen_captcp_ss = h1.popen("pwd") # 10Hz
    h1.cmdPrint("iperf -c 10.0.0.2")
    #popen_iperf = h1.popen("iperf -c 10.0.0.2")
    #time.sleep(3)

    time.sleep(1)
    print "Parando tcpdump"
    h1.killPid(pid_tcpdump)
    time.sleep(1)
    print "Parando captcp"
    h1.killPid(pid_captcp_ss)
    time.sleep(10)
    #popen_captcp_ss.send_signal(signal.SIGINT)
    #h1.sendInt(chr(signal.SIGINT))
    #print h1.waitOutput()
    print "Parando iperf"
    h2.killPid(pid_iperf)
    #salida = pmonitor({"a": popen_captcp_ss}, timeoutms=500)
    #for h, l in salida:
    #    print "ASD"
    #    print l

    print "Graficando socketstatistic"
    
    h1.cmd("pushd ./captcp_ss")
    h1.cmd("make")
    h1.cmd("popd")
    
    print "Determinando el numero de flow capturado"

    salida = h1.cmd("captcp statistic ./trace.pcap | grep -E 'Flow|Data application layer' | ansi2txt")
    flow = parse.parse_captcp_stat(salida)
    
    print "Graficando throughput"

    h1.cmd('mkdir -p "./captcp_throughput"')
    h1.cmd(
        "captcp throughput -s {sample_len} -i -u Mbit \
        -f {flow} -o {output_dir} {pcap}".format(
            sample_len="0.1",
            flow=flow,
            output_dir="./captcp_throughput",
            pcap="./trace.pcap"
        )
    )
    h1.cmd("pushd ./captcp_throughput")
    h1.cmd("make")
    h1.cmd("popd")
    
    print "Graficar inflight"

    h1.cmd('mkdir -p "./captcp_inflight"')
    h1.cmd(
        "captcp inflight -i -f {flow} -o {output_dir} {pcap}".format(
            flow=flow,
            output_dir="./captcp_inflight",
            pcap="./trace.pcap"
        )
    )
    h1.cmd("pushd ./captcp_inflight")
    h1.cmd("make")
    h1.cmd("popd")

    # --------------------------------------------------------------------------
    # Ver que se hayan cerrado los procesos

    time.sleep(1)
    if h1.waiting:
        print "Proceso de h1 no salio"
    if h2.waiting:
        print "Proceso de h2 no salio"
    if not h1.waiting and not h2.waiting:
        print "Los procesos de h1 y h2 terminaron"

if __name__ == '__main__':
    setLogLevel( 'info' )
    myNetwork()
