#!/usr/bin/python

import time
import signal
import os
import shutil
import sys
import itertools
from glob import glob

# Importar mininet

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

# Importar modulos presentes en esta carpeta

import parse
from plot import plot

class MiHost(Host):
    """
    Host con algunas funciones mas.

    Hay varias funciones para correr comandos, provenientes de Mininet y documentadas en
    http://mininet.org/api/classmininet_1_1node_1_1Node.html.

    Las mas utiles son:

    - self.cmd(): Correr un comando comun y esperar a que termine.

    - self.cmdPrint(): Correr un comando mostrando la salida y esperar a que termine.

    En esta clase se definen mas funciones, ver abajo.
    """

    def __init__(self, *args, **kwargs):
        super(MiHost, self).__init__(*args, **kwargs)

    def config(self, **params):
        super(MiHost, self).config(**params)

    def cmdBack(self, *cmd):
        """
        Corre un comando en el fondo y devuelve su PID.
        """
        cmd = cmd + ("&",)
        self.cmd(*cmd)
        return int(self.cmd("echo $!"))

    def cmdLog(self, log_file, *cmd):
        """
        Corre un comando y guarda la salida en el archivo de log.
        """
        log_file.write("Host: {} ----------------------------\n".format(self.name))
        log_file.write(str(cmd) + "\n")
        log_file.write(str(self.cmd(*cmd)) + "\n")

    def killPid(self, pid):
        """
        Manda Ctrl-C a un proceso dado su PID.
        """
        self.cmd("kill -INT {}".format(pid))

def run_test(test):
    """
    Crear una topologia completa y correr una prueba.

    Se debe dar como argumento un obeto TestDef, que contiene los parametros de la prueba
    """
    
    shutil.rmtree(test.folder, ignore_errors=True)
    os.makedirs(test.folder)
    
    with open(test.log_path, "w") as log_file:

        log_file.write("------------------------------\n")
        log_file.write(str(test) + "\n")
        print ""
        print "------------------------------"
        print str(test)
        print ""

        # ------------------------------------------------------------------
        # Crear topologia, configurar IPs, etc.
        print "Creando topologia"

        net = Mininet(topo=None, build=False)

        netem = net.addHost('netem', cls=MiHost, defaultRoute=None)
        h1 = net.addHost('h1', cls=MiHost, ip='10.0.0.10/8', defaultRoute='10.0.0.1')
        h2 = net.addHost('h2', cls=MiHost, ip='11.0.0.10/8', defaultRoute='11.0.0.1')

        netem_int1 = net.addLink(h1, netem).intf2
        netem_int2 = net.addLink(h2, netem).intf2

        net.build()
        net.start()

        time.sleep(1)
        
        print "Configurando hosts"

        netem_int1.setIP("10.0.0.1/8")
        netem_int2.setIP("11.0.0.1/8")

        h1.cmd(
            "ip r add default via 10.0.0.1")
        h2.cmd(
            "ip r add default via 11.0.0.1")

        netem.cmd(
            "echo 1 > /proc/sys/net/ipv4/ip_forward")
        netem.cmdLog(log_file,
            "ip -c a")
        h1.cmdLog(log_file,
            "ip -c a")
        h2.cmdLog(log_file,
            "ip -c a")

        h1.cmd(
            "modprobe tcp_bbr")
        h2.cmd(
            "modprobe tcp_bbr")

        h1.cmd(
            "sysctl -w net.ipv4.tcp_congestion_control={}".format(test.tcp_cc))
        h2.cmd(
            "sysctl -w net.ipv4.tcp_congestion_control={}".format(test.tcp_cc))
            
        h1.cmdLog(log_file,
            "sysctl net.ipv4.tcp_congestion_control")
        h2.cmdLog(log_file,
            "sysctl net.ipv4.tcp_congestion_control")

        net.pingAll()

        for controller in net.controllers:
            controller.start()

        # --------------------------------------------------------------------------
        # Configurar netem
        print "Configurando netem"

        # Poner netem solo en la interfaz de ida

        intf = netem_int2.name

        netem.cmd(
            "tc qdisc del dev {intf} root".format(intf=intf))

        if test.loss > 0:
            loss_params = "loss {}% ".format(test.loss)
        else:
            loss_params = ""

        if test.delay > 0 or test.jitter > 0:
            delay_params = "delay {}ms {}ms {}%".format(test.delay, test.jitter, test.corr)
        else:
            delay_params = ""

        netem.cmd(
            "tc qdisc add dev {intf} root handle 1: netem {loss_params} {delay_params}"
                .format(intf=intf, loss_params=loss_params, delay_params=delay_params))

        if test.limit:
            buf_params = "limit {}".format(test.limit)
        else:
            buf_params = "latency {}ms".format(test.latency)

        netem.cmd(
            "tc qdisc add dev {intf} parent 1: handle 2: tbf rate {bw}mbit burst {burst}kb {buf_params}"
                .format(intf=intf, bw=test.bw, burst=test.burst, buf_params=buf_params))
                
        netem.cmdLog(log_file,
            "tc qdisc show")

        # --------------------------------------------------------------------------
        # Crear carpetas temporales y moverse ahi
        print "Preparando prueba"

        h1.cmd((
            "mkdir -p {test_folder}/h1;"
            "cd {test_folder}/h1;").format(test_folder=test.folder))

        h2.cmd((
            "mkdir -p {test_folder}/h2;"
            "cd {test_folder}/h2;").format(test_folder=test.folder))

        netem.cmd((
            "mkdir -p {test_folder}/netem;"
            "cd {test_folder}/netem;").format(test_folder=test.folder))

        # --------------------------------------------------------------------------
        # Iperf3. Cliente (h1) manda a servidor (h2)

        # Iniciar servidor

        # El /dev/null es para que no imprima nada en pantalla
        pid_iperf = h2.cmdBack(
            "iperf -s > /dev/null")
        time.sleep(1)

        # Iniciar capturas

        h1.cmd(
            "mkdir ./captcp_ss")
        pid_tcpdump = h1.cmdBack(
            "tcpdump -i h1-eth0 -w ./trace.pcap")
            
        # El /dev/null es para que no imprima nada en pantalla
        pid_captcp_ss = h1.cmdBack(
            "captcp socketstatistic -s 100 -o ./captcp_ss > /dev/null") # 100Hz
        pid_qlen = netem.cmdBack(
            "qlen_plot.py {}".format(intf))

        # Iniciar iperf
        print "Haciendo prueba..."

        h1.cmdLog(log_file,
            "iperf -c 11.0.0.10 -t {}".format(test.duration))

        # Parar capturas

        time.sleep(1)
        print "Parando tcpdump"
        h1.killPid(pid_tcpdump)
        print "Parando captcp"
        h1.killPid(pid_captcp_ss)
        print "Parando iperf"
        time.sleep(2)
        h2.killPid(pid_iperf)
        print "Parando qlen_plot"
        netem.killPid(pid_qlen)

        # Analizar throughput

        print "Determinando el numero de flow capturado"

        salida = h1.cmd(
            "captcp statistic ./trace.pcap | grep -E 'Flow|Data application layer' | ansi2txt")
        flow = parse.parse_captcp_stat(salida)

        print "Analizando throughput"

        h1.cmdLog(log_file, (
            'mkdir -p "./captcp_throughput";'
            "captcp throughput -ps 0.1 -i -u Mbit -f {flow} -o ./captcp_throughput ./trace.pcap;")
                .format(flow=flow))

        # Analizar inflight

        print "Analizando inflight"

        h1.cmdLog(log_file, (
            "mkdir -p ./captcp_inflight;"
            "captcp inflight -i -f {flow} -o ./captcp_inflight ./trace.pcap;")
                .format(flow=flow))

        h1.cmd(
            "rm ./trace.pcap")

        # Graficando con matplotlib
        print "Graficando con matplotlib"

        plot(
            name=test.name,
            data_paths={
                "throughput": "{}/h1/captcp_throughput/throughput.data".format(test.folder),
                "inflight": "{}/h1/captcp_inflight/inflight.data".format(test.folder),
                "rtt": glob("{}/h1/captcp_ss/*:5001/rtt/rtt.data".format(test.folder))[0],
                "cwnd": glob("{}/h1/captcp_ss/*:5001/cwnd-ssthresh/cwnd.data".format(test.folder))[0],
                "qlen": "{}/netem/qlen.data".format(test.folder),
            },
            out_path=test.resfolder,
        )

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
        burst=32, # Tamano del burst en kbytes, ver manual de tbf
        latency=50, # Maximo delay del buffer en ms
        limit=None, # Tamano del buffer en bytes, es una alternativa a latency
        delay=0, # Delay de enlaces en ms, el RTT deberia ser el doble
        jitter=0, # Jitter en ms
        corr=25, # Correlacion del jitter en porcentaje (1 = 1%)
        loss=0, # Perdida en porcentaje (1 = 1%)
        duration=20 # Duracion de prueba en segundos
    ):
        TestDef.total_tests += 1

        # Numero de test
        self.test_num = TestDef.total_tests

        self.tcp_cc = tcp_cc
        self.bw = bw
        self.burst = burst
        self.latency = latency
        self.limit = limit
        self.delay = delay
        self.jitter = jitter
        self.corr = corr
        self.loss = loss
        self.duration = duration

        # Nombre unico, pensado para usarse como nombre de archivo
        self.name = "{test_num}_{tcp_cc}_{bw}mbps_buf{latency}ms_limit{limit}_{delay}~{jitter}ms_{loss}%".format(
            tcp_cc=tcp_cc,
            bw=bw,
            burst=burst,
            latency=latency,
            limit=limit,
            delay=delay,
            jitter=jitter,
            corr=corr,
            loss=loss,
            test_num=self.test_num,
        )

        self.folder = "/var/tmp/mininet/{}/".format(self.name)

        self.resfolder = "/var/tmp/mininet/results/"

        self.log_path = "{}/log.txt".format(self.folder)

    def __str__(self):
        """
        Se imprime a si mismo para loguearse
        """
        return self.name


def main(escenario):
    # Borrar resultados de pruebas anteriores
    shutil.rmtree("/var/tmp/mininet", ignore_errors=True)
    
    if escenario == 1:

        tests = []

        tcp_ccs = ["reno", "cubic", "bbr", "bbr2"]

        for tcp_cc in tcp_ccs:

            tests.append(TestDef(
                tcp_cc=tcp_cc,
                bw=10, # Mbps
                burst=32, # kbytes
                latency=50, # ms
                delay=100, # ms
                jitter=0, # ms
                corr=25, # %
                loss=0, # %
                duration=20 # s
            ))

        for t in tests:
            run_test(t)

    elif escenario == 2:

        tests = []

        tcp_ccs = ["bbr", "bbr2"]

        for tcp_cc in tcp_ccs:
            bw = 100
            tests.append(TestDef(
                tcp_cc=tcp_cc,
                bw=bw, # Mbps
                burst=int(bw*1000/250/8), # kbytes, https://unix.stackexchange.com/a/100797
                latency=30, # ms
                delay=30, # ms
                jitter=0, # ms
                corr=25, # %
                loss=0, # %
                duration=60 # s
            ))

        for t in tests:
            run_test(t)

    elif escenario == 3:

        tests = []

        tcp_ccs = ["reno", "cubic", "bbr", "bbr2"]

        for tcp_cc in tcp_ccs:
            bw = 100
            tests.append(TestDef(
                tcp_cc=tcp_cc,
                bw=bw, # Mbps
                burst=int(bw*1000/250/8), # kbytes, https://unix.stackexchange.com/a/100797
                latency=100, # ms
                delay=100, # ms
                jitter=0, # ms
                corr=25, # %
                loss=0.5, # %
                duration=10 # s
            ))

        for t in tests:
            run_test(t)

    elif escenario == 4:

        tests = []

        tcp_ccs = ["reno", "bbr", "bbr2"]

        for tcp_cc in tcp_ccs:
            bw = 100
            tests.append(TestDef(
                tcp_cc=tcp_cc,
                bw=bw, # Mbps
                burst=int(bw*1000/250/8), # kbytes, https://unix.stackexchange.com/a/100797
                latency=50, # ms
                delay=50, # ms
                jitter=0, # ms
                corr=25, # %
                loss=0, # %
                duration=60 # s
            ))

        for t in tests:
            run_test(t)

    elif escenario == 5:

        tests = []

        tcp_ccs = ["reno", "bbr", "bbr2"]
        bw = 100
        delay = 200
        BDP = int(bw*1000000 * delay/1000)

        for tcp_cc in tcp_ccs:
            tests.append(TestDef(
                tcp_cc=tcp_cc,
                bw=bw, # Mbps
                burst=int(bw*1000/250/8), # kbytes, https://unix.stackexchange.com/a/100797
                limit=int(BDP/100), # bytes
                delay=50, # ms
                jitter=0, # ms
                corr=25, # %
                loss=0, # %
                duration=60 # s
            ))

        for t in tests:
            run_test(t)

    elif escenario == 0:

        tests = []

        tcp_ccs = ["bbr", "bbr2"]
        bws = [100] # Mbps
        latencies = [30] # ms
        delays = [30] # ms
        jitters = [0] # ms
        corrs = [25] # %
        losses = [0] # %

        for tcp_cc, bw, latency, delay, jitter, corr, loss in itertools.product(
                tcp_ccs, bws, latencies, delays, jitters, corrs, losses):

            BDP = bw*1000000 * delay/1000
            tests.append(TestDef(
                tcp_cc=tcp_cc,
                bw=bw, # Mbps
                burst=int(bw*1000/250/8), # kbytes, https://unix.stackexchange.com/a/100797
                latency=latency, # ms
                delay=delay, # ms
                jitter=jitter, # ms
                corr=corr, # %
                loss=loss, # %
                duration=10 # s
            ))

        for t in tests:
            run_test(t)
            
    else:
        print("Escenario {} no existe".format(escenario))

if __name__ == '__main__':
    setLogLevel( 'warning' )

    try:
        escenario = int(sys.argv[1])
    except:
        print "Ejecutar programa indicando el numero de escenario como argumento"
        sys.exit()

    main(escenario)
