import parse

def test_parse():
    text = """# captcp 2010-2013 Hagen Paul Pfeifer and others (c)
    # http://research.protocollabs.com/captcp/
    30351 packets captured
    693909 packets received by filter
    663526 packets dropped by kernel
    Flow 1.1  10.0.0.1:40754 -> 10.0.0.2:5201
    Flow 1.2  10.0.0.2:5201 -> 10.0.0.1:40754
    Data application layer:                           0 bytes     Data application layer:                           2 bytes  
    Flow 2.1  10.0.0.1:40756 -> 10.0.0.2:5201
    Flow 2.2  10.0.0.2:5201 -> 10.0.0.1:40756
    Data application layer:                    4313671224 bytes     Data application layer:                             0 bytes  
    """
    flow = parse.parse_captcp_stat(text)

    assert flow == "2.1"
