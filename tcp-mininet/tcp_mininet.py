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
from plot import plot

import time
import signal
import shutil
import itertools
from glob import glob

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
    # Crear topologia, configurar IPs, etc.
    
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
    
    h1.cmd("modprobe tcp_bbr")
    h2.cmd("modprobe tcp_bbr")

    h1.cmd("sysctl -w net.ipv4.tcp_congestion_control={}".format(test.tcp_cc))
    h2.cmd("sysctl -w net.ipv4.tcp_congestion_control={}".format(test.tcp_cc))

    net.pingAll()

    for controller in net.controllers:
        controller.start()

    # --------------------------------------------------------------------------
    # Configurar netem

    # Poner netem solo en la interfaz de ida

    intf = netem_int2.name

    netem.cmd("tc qdisc del dev {intf} root".format(intf=intf))

    if test.loss > 0:
        loss = "loss {}% ".format(test.loss)
    else:
        loss = ""

    netem.cmdPrint(("tc qdisc add dev {intf} root handle 1: netem "
                "{loss} delay {delay}ms {jitter}ms {corr}%").format(
            intf=intf,
            loss=loss,
            delay=test.delay,
            jitter=test.jitter,
            corr=test.corr,
        ))

    if test.limit:
        buf_params = "limit {}".format(test.limit)
    else:
        buf_params = "latency {}ms".format(test.latency)

    netem.cmdPrint(("tc qdisc add dev {intf} parent 1: handle 2: tbf "
               "rate {bw}mbit burst {burst}kb {buf_params}").format(
            intf=intf,
            bw=test.bw,
            burst=test.burst,
            buf_params=buf_params,
        ))

    # --------------------------------------------------------------------------
    # Crear carpetas temporales y moverse ahi

    h1.cmd("rm -r {}".format(test.folder))
    h1.cmd("mkdir -p {}/h1".format(test.folder))
    h1.cmd("cd {}/h1".format(test.folder))

    h2.cmd("mkdir -p {}/h2".format(test.folder))
    h2.cmd("cd {}/h2".format(test.folder))
    
    netem.cmd("mkdir -p {}/netem".format(test.folder))
    netem.cmd("cd {}/netem".format(test.folder))

    h1.cmd("mkdir -p ~/resultados/")
    
    # --------------------------------------------------------------------------
    # Empezar a loguear info

    with open(test.log_path, "w") as log_file:

        log_file.write(str(test) + "\n")
        log_file.write("------------------------------\n")
        
        netem.logCmd(log_file, "tc qdisc show")
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
        # Iperf3. Cliente (h1) manda a servidor (h2)

        # Iniciar servidor
        
        # El  /dev/null es para que no imprima nada en pantalla
        pid_iperf = h2.bgCmd("iperf -s > /dev/null")
        time.sleep(1)
        
        # Iniciar capturas

        h1.cmd("mkdir ./captcp_ss")
        pid_tcpdump = h1.bgCmd("tcpdump -i h1-eth0 -w ./trace.pcap")
        pid_captcp_ss = h1.bgCmd("captcp socketstatistic -s 100 -o ./captcp_ss") # 100Hz
        pid_qlen = netem.bgCmd("qlen_plot.py {}".format(intf))
        
        # Iniciar iperf
        
        h1.logCmd(log_file, "iperf -c 11.0.0.10 -t {}".format(test.duration))

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
        
        # Graficar socketstatistic

        print "Graficando socketstatistic"
        
        h1.cmd("pushd ./captcp_ss/*:5001")
        
        h1.cmd("pushd ./cwnd-ssthresh")
        h1.logCmd(log_file, "make")
        h1.cmd("mkdir -p {}/ssthreshs/".format(test.resfolder))
        h1.cmd("cp *.pdf {}/ssthreshs/{}.pdf".format(test.resfolder, test.name))
        h1.cmd("popd")
        
        h1.cmd("pushd ./rtt")
        h1.logCmd(log_file, "make")
        h1.cmd("mkdir -p {}/rtts/".format(test.resfolder))
        h1.cmd("cp *.pdf {}/rtts/{}.pdf".format(test.resfolder, test.name))
        h1.cmd("popd")
        
        h1.cmd("pushd ./skmem")
        h1.logCmd(log_file, "make")
        h1.cmd("popd")
        
        h1.cmd("popd")
        
        # Graficar throughput
        
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
        h1.cmd("mkdir -p {}/throughputs/".format(test.resfolder))
        h1.cmd("cp *.pdf {}/throughputs/{}.pdf".format(test.resfolder, test.name))
        h1.cmd("popd")
        
        # Graficar inflight
        
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
        h1.cmd("mkdir -p {}/inflights/".format(test.resfolder))
        h1.cmd("cp *.pdf {}/inflights/{}.pdf".format(test.resfolder, test.name))
        h1.cmd("popd")
        
        h1.cmd("rm ./trace.pcap")
        
        # Copiar grafico de qlen
        
        netem.cmd("mkdir -p {}/qlen/".format(test.resfolder))
        netem.cmd("cp ./*.png {}/qlen/{}.png".format(test.resfolder, test.name))
        
        # Graficando con matplotlib
        
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
        
        self.resfolder = "/var/tmp/mininet/res/"
        
        self.log_path = "{}/log.txt".format(self.folder)
        
    def __str__(self):
        """
        Se imprime a si mismo para loguearse
        """
        return self.name
        
def escenario_1():
    
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
        
def escenario_2():
    
    tests = []
    
    tcp_ccs = ["bbr", "bbr2"]
    
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
            loss=0, # %
            duration=60 # s
        ))
    
    for t in tests:
        run_test(t)
        
def escenario_3():
    
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
        
def escenario_4():
    
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
        
def escenario_5():
    
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
        
def prueba():
    
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
            duration=60 # s
        ))
    
    for t in tests:
        run_test(t)

if __name__ == '__main__':
    setLogLevel( 'info' )
    
    shutil.rmtree("/var/tmp/mininet", ignore_errors=True)
    
    escenario_3()
    # TODO: Tomar desde argv

