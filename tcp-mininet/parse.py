def parse_captcp_stat(text):
    """
    Busca el flujo que se corresponde a prueba de iperf.

    Se debe dar como argumento el texto de stdout de
    `captcp statistic | grep -E 'Flow|Data application layer`.

    Ejemplo de salida:

        # captcp 2010-2013 Hagen Paul Pfeifer and others (c)
        # http://research.protocollabs.com/captcp/
        30351 packets captured
        693909 packets received by filter
        663526 packets dropped by kernel
        Flow 1.1  10.0.0.1:40754 -> 10.0.0.2:5201
        Flow 1.2  10.0.0.2:5201 -> 10.0.0.1:40754
        Data application layer: 0 bytes Data application layer: 2 bytes  
        Flow 2.1  10.0.0.1:40756 -> 10.0.0.2:5201
        Flow 2.2  10.0.0.2:5201 -> 10.0.0.1:40756
        Data application layer: 4313671224 bytes Data application layer: 0 bytes
        
    En realidad las primeras lineas que empiezan con # y las que
    empiezan con numeros vienen de stderr. Parece que mininet mezcla
    stdout y stderr. Entonces ignoro primeras lineas.

    Va a buscar el flujo con mas bits transmitidos.
    """

    def group(iterator, count):
        # Ignorar las lineas de stderr
        itr = iter(
            filter(
                lambda line: line.strip().startswith("Flow") \
                             or line.strip().startswith("Data application layer"),
                iterator
            )
        )
        # Dar tuples de a tres elementos
        while True:
            yield tuple([itr.next() for i in range(count)])


    flow = ("0.1", 0)

    for lines in group(iter(text.splitlines()), 3):
        flow1 = lines[0].strip().split()[1]
        flow2 = lines[1].strip().split()[1]
        data1 = int(lines[2].strip().split()[3])
        data2 = int(lines[2].strip().split()[8])

        if data1 > flow[1]:
            flow = (flow1, data1)
        if data2 > flow[1]:
            flow = (flow2, data2)


    return flow[0]
