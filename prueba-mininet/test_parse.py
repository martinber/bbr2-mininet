def group(iterator, count):
    itr = iter(iterator)
    while True:
        yield tuple([itr.next() for i in range(count)])


def test_parse():
    text = """Flow 1.1  10.0.0.1:40754 -> 10.0.0.2:5201
   Flow 1.2  10.0.0.2:5201 -> 10.0.0.1:40754
   Data application layer:                           0 bytes     Data application layer:                           2 bytes  
   Flow 2.1  10.0.0.1:40756 -> 10.0.0.2:5201
   Flow 2.2  10.0.0.2:5201 -> 10.0.0.1:40756
   Data application layer:                    4313671224 bytes     Data application layer:                             0 bytes  
"""
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

    assert flow == ("2.1", 4313671224)
