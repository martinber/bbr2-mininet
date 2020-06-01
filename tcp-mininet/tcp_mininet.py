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
import shutil

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
        self.cmd(*cmd)
        return int(self.cmd("echo $!"))
        
    def logCmd(self, log_file, *cmd):
        """
        Corre un comando y guarda la salida en el archivo de log
        """
        log_file.write("Host: {} ----------------------------\n".format(self.name))
        log_file.write(str(cmd) + "\n")
        log_file.write(str(self.cmd(*cmd)) + "\n")
        
    def killPid(self, pid):
        """
        Manda Ctrl-C a un proceso dado su PID.
        """
        self.cmdPrint("kill -INT {}".format(pid))

def run_test(test):

    # ------------------------------------------------------------------
    # Crear topologia
    
    net = Mininet(topo=None,
                  build=False)

    info( '*** Iniciando\n')

    netem = net.addHost('netem', cls=MiHost, defaultRoute=None)

    h1 = net.addHost('h1', cls=MiHost, ip='10.0.0.10/8', defaultRoute='10.0.0.1')
    h2 = net.addHost('h2', cls=MiHost, ip='11.0.0.10/8', defaultRoute='11.0.0.1')

    netem_int1 = net.addLink(h1, netem).intf2
    netem_int2 = net.addLink(h2, netem).intf2
    
    net.build()
    net.start()

    time.sleep(1)
    
    netem_int1.setIP("10.0.0.1/8")
    netem_int2.setIP("11.0.0.1/8")
    
    h1.cmd("ip r add default via 10.0.0.1")
    h2.cmd("ip r add default via 11.0.0.1")

    netem.cmd("echo 1 > /proc/sys/net/ipv4/ip_forward")
    netem.cmdPrint("ip -c a")
    h1.cmdPrint("ip -c a")
    h2.cmdPrint("ip -c a")

    net.pingAll()

    for controller in net.controllers:
        controller.start()

    # --------------------------------------------------------------------------
    # Inicializar

    h1.cmd("modprobe tcp_bbr")
    h2.cmd("modprobe tcp_bbr")

    h1.cmd("sysctl -w net.ipv4.tcp_congestion_control={}".format(test.tcp_cc))
    h2.cmd("sysctl -w net.ipv4.tcp_congestion_control={}".format(test.tcp_cc))


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
        
        h1.logCmd(log_file, "sysctl net.ipv4.tcp_congestion_control")
        h2.logCmd(log_file, "sysctl net.ipv4.tcp_congestion_control")

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
        pid_captcp_ss = h1.bgCmd("captcp socketstatistic -s 50 -o ./captcp_ss") # 10Hz
        h1.logCmd(log_file, "iperf -c 11.0.0.10 -t 20")

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
        h1.logCmd(log_file, "make")
        h1.cmd("popd")
        
        h1.cmd("pushd ./rtt")
        h1.logCmd(log_file, "make")
        h1.cmd("popd")
        
        h1.cmd("pushd ./skmem")
        h1.logCmd(log_file, "make")
        h1.cmd("popd")
        
        h1.cmd("popd")
        
        print "Determinando el numero de flow capturado"

        salida = h1.cmd("captcp statistic ./trace.pcap | grep -E 'Flow|Data application layer' | ansi2txt")
        flow = parse.parse_captcp_stat(salida)
        
        print "Graficando throughput"

        h1.cmd('mkdir -p "./captcp_throughput"')
        h1.cmd(
            "captcp throughput -ps {sample_len} -i -u Mbit \
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
        
        h1.cmd("rm ./trace.pcap")

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
        tcp_cc="reno", # Congestion control: reno, cubic, bbr, bbr2
        bw=100, # Ancho de banda de enlaces en Mbitps
        delay=0, # Delay de enlaces en ms, el RTT deberia ser el doble
        jitter=0, # Jitter en ms
        loss=None, # Perdida en porcentaje (1 = 1%), o None
        max_queue_size=None, # Tamano de cola en paquetes de cada enlace.
                             # Vendria a ser el limit de netem
    ):
        TestDef.total_tests += 1
        
        # Numero de test
        self.test_num = TestDef.total_tests
        
        self.tcp_cc = tcp_cc
        self.bw = bw
        self.delay = delay
        self.jitter = jitter
        self.loss = loss
        self.max_queue_size = max_queue_size
        
        # Nombre unico, pensado para usarse como nombre de archivo
        self.name = "{tcp_cc}_{bw}mbps_{delay}~{jitter}ms_{loss}%_{queue}pkt".format(
            tcp_cc=tcp_cc,
            bw=bw,
            delay=delay,
            jitter=jitter,
            loss=loss,
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
            "jitter": "{}ms".format(self.jitter),
            "loss": self.loss,
            "max_queue_size": self.max_queue_size,
        }
        
    def __str__(self):
        """
        Se imprime a si mismo para loguearse
        """
        return self.name

if __name__ == '__main__':
    setLogLevel( 'info' )
    
    shutil.rmtree("/var/tmp/mininet", ignore_errors=True)
    
    tests = [
        TestDef(
            tcp_cc="reno",
            bw=10, # Mbps
            delay=100, # ms
            jitter=0, # ms
            loss=None, # %
            max_queue_size=None, # paquetes
        ),
        
    ]
    
    for t in tests:
        run_test(t)
