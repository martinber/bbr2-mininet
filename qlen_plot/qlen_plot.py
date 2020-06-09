#!/usr/bin/env python3

# Mininet 2.3.0d6 License
# 
# Copyright (c) 2013-2019 Open Networking Laboratory
# Copyright (c) 2009-2012 Bob Lantz and The Board of Trustees of
# The Leland Stanford Junior University
# 
# Original authors: Bob Lantz and Brandon Heller
# 
# We are making Mininet available for public use and benefit with the
# expectation that others will use, modify and enhance the Software and
# contribute those enhancements back to the community. However, since we
# would like to make the Software available for broadest use, with as few
# restrictions as possible permission is hereby granted, free of charge, to
# any person obtaining a copy of this Software to deal in the Software
# under the copyrights without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 
# The name and trademarks of copyright holder(s) may NOT be used in
# advertising or publicity pertaining to the Software or any derivatives
# without specific, written prior permission.

from time import sleep, time
from subprocess import *
import re
import sys
import signal

import matplotlib.pyplot as plt
 
def monitor_qlen(intf, interval_sec=0.01):
    # enp0s3qdisc fq_codel 0: root refcnt 2 limit 10240p flows 1024 quantum 1514 target 5.0ms interval 100.0ms memory_limit 32Mb ecn 
    #  Sent 78391 bytes 1185 pkt (dropped 0, overlimits 0 requeues 0) 
    #  backlog 0b 0p requeues 0
    #   maxpacket 0 drop_overlimit 0 new_flow_count 0 ecn_mark 0
    #   new_flows_len 0 old_flows_len 0

    signal.signal(signal.SIGINT, signal.default_int_handler)

    pat_queued = re.compile(r'backlog\s[^\s]+\s([\d]+)p')
    cmd = "tc -s qdisc show dev {}".format(intf)
    
    t_values = []
    y_values = []

    try:
        with open("qlen.txt","w") as out_file:
            out_file.write('')
            t0 = "%f" % time()
            while 1: 
                p = Popen(cmd, shell=True, stdout=PIPE)
                output = p.stdout.read().decode("utf-8")
                matches = pat_queued.findall(output)
                print(matches)
                if matches and len(matches) > 1:
                    t1 = "%f" % time()
                    t = float(t1)-float(t0)
                    y = int(matches[1])
                    t_values.append(t)
                    y_values.append(y)
                    print(t, y)
                    out_file.write(str(t)+' '+str(y)+'\n')
                    sleep(interval_sec)
    except KeyboardInterrupt:
        print("Parado de monitorear") 
    
        fig = plt.figure()
        ax = fig.subplots(1,1)
        ax.plot(t_values, y_values)
        fig.savefig("grafico.png")
        print("Terminado")

if __name__ == "__main__":

    if len(sys.argv) != 2 or sys.argv[1] == "-h":
        print("Dar nombre de interfaz como argumento")
    else:
        monitor_qlen(sys.argv[1])
