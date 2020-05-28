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

def run_test(test):

    # ------------------------------------------------------------------
    # Crear topologia
    
    net = Mininet(topo=None,
                  build=False,
                  ipBase='10.0.0.0/8')

    info( '*** Iniciando\n')
    s1 = net.addSwitch('s1', cls=OVSKernelSwitch, failMode='standalone')

    h1 = net.addHost('h1', cls=MiHost, ip='10.0.0.1', defaultRoute=None)
    h2 = net.addHost('h2', cls=MiHost, ip='10.0.0.2', defaultRoute=None)

    net.addLink(h1, s1, cls=TCLink, **test.get_link_params())
    net.addLink(h2, s1, cls=TCLink, **test.get_link_params())

    net.build()

    for controller in net.controllers:
        controller.start()

    net.get('s1').start([])

    # --------------------------------------------------------------------------
    # Inicializar

    h1.cmd("modprobe tcp_bbr")
    h2.cmd("modprobe tcp_bbr2")

    # --------------------------------------------------------------------------
    # Crear carpetas temporales y moverse ahi

    h1.cmd("rm -r {}".format(test.folder))
    h1.cmd("mkdir -p {}/h1".format(test.folder))
    h1.cmd("cd {}/h1".format(test.folder))

    h2.cmd("mkdir -p {}/h2".format(test.folder))
    h2.cmd("cd {}/h2".format(test.folder))

    h1.cmd("mkdir -p ~/resultados/")
    
    # --------------------------------------------------------------------------
    # Empezar a loguear info

    with open(test.log_path, "w") as log_file:

        log_file.write(str(test) + "\n")
        log_file.write("------------------------------\n")

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

        pid_tcpdump = h1.bgCmd("tcpdump -s 96 -i h1-eth0 -w ./trace.pcap")
        h1.cmd("mkdir ./captcp_ss")
        pid_captcp_ss = h1.bgCmd("captcp socketstatistic -s 50 -o ./captcp_ss") # 10Hz
        h1.cmdPrint("iperf -c 10.0.0.2 -t 20")

        time.sleep(1)
        
        print "Parando tcpdump"
        h1.killPid(pid_tcpdump)
        print "Parando captcp"
        h1.killPid(pid_captcp_ss)
        time.sleep(2)
        print "Parando iperf"
        h2.killPid(pid_iperf)

        print "Graficando socketstatistic"
        
        h1.cmd("pushd ./captcp_ss/*:5001")
        
        h1.cmd("pushd ./cwnd-ssthresh")
        h1.cmdPrint("pwd")
        h1.cmdPrint("make")
        h1.cmd("popd")
        
        h1.cmd("pushd ./rtt")
        h1.cmdPrint("make")
        h1.cmd("popd")
        
        h1.cmd("pushd ./skmem")
        h1.cmdPrint("make")
        h1.cmd("popd")
        
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
        
    net.stop()
        
class TestDef:
    
    total_tests = 0 # Llevar cuenta de cantidad de tests
    
    def __init__(
        self,
        tcp_cc, # Congestion control: reno, cubic, bbr, bbr2
        bw, # Ancho de banda de enlaces en kbps?
        delay, # Delay de enlaces en ms, el RTT deberia ser el doble
        max_queue_size, # Tamano de cola de cada enlace
    ):
        TestDef.total_tests += 1
        
        # Numero de test
        self.test_num = TestDef.total_tests
        
        self.tcp_cc = tcp_cc
        self.bw = bw
        self.delay = delay
        self.max_queue_size = max_queue_size
        
        # Nombre unico, pensado para usarse como nombre de archivo
        self.name = "{tcp_cc}_{bw}k_{delay}ms_{queue}pkt".format(
            tcp_cc=tcp_cc,
            bw=bw,
            delay=delay,
            queue=max_queue_size,
        )
        
        self.folder = "/var/tmp/mininet/{}/".format(self.name)
        
        self.log_path = "{}/log.txt".format(self.folder)
        
    def get_link_params(self):
        """
        Devuelve parametros a usar en los links
        """
        return {
            "bw": self.bw,
            "delay": "{}ms".format(self.delay),
            "max_queue_size": self.max_queue_size,
        }

if __name__ == '__main__':
    setLogLevel( 'info' )
    
    
    tests = [
        TestDef(
            tcp_cc="reno",
            bw=10000,
            delay=100,
            max_queue_size=100,
        ),
        TestDef(
            tcp_cc="reno",
            bw=100000,
            delay=100,
            max_queue_size=100,
        ),
        TestDef(
            tcp_cc="reno",
            bw=1000000,
            delay=100,
            max_queue_size=100,
        ),
    ]
    
    for t in tests:
        run_test(t)
