import matplotlib.pyplot as plt

def plot(name, data_paths, out_path):
    """
    name se usa para guardar cada grafico con un nombre unico. Por
    ejemplo es "4_bbr2_10mbps_buf50ms_limitNone_100~0ms_0%"
    
    data_paths es un diccionario de las rutas a los archivos .data a
    graficar. Por ejemplo:
    
    {
        "qlen": "/var/tmp/mininet/test1/netem/qlen.data",
        "inflight": "/var/tmp/mininet/test1/h1/inflight/inflight.data",
        "throughput": ....,
        "rtt": ....,
        "cwnd": ....,
    }
    
    out_path es la carpeta donde se guardan los graficos
    """

    plots = [
        {
            "type": "qlen",
            "data_path": data_paths["qlen"],
            "y_label": "Longitud de cola [paquetes]",
            "x_label": "Tiempo [s]",
        },
        {
            "type": "inflight",
            "data_path": data_paths["inflight"],
            "y_label": "Paquetes en transito [paquetes]",
            "x_label": "Tiempo [s]",
        },
        {
            "type": "throughput",
            "data_path": data_paths["throughput"],
            "y_label": "Ancho de banda [Mbps]",
            "x_label": "Tiempo [s]",
        },
        {
            "type": "rtt",
            "data_path": data_paths["rtt"],
            "y_label": "Tiempo de ida y vuelta [ms]",
            "x_label": "Tiempo [s]",
        },
        {
            "type": "cwnd",
            "data_path": data_paths["cwnd"],
            "y_label": "Ventana de congestion [paquetes]",
            "x_label": "Tiempo [s]",
        },
    ]
    
    with plt.style.context("ggplot"):

        for p in plots:

            fig = plt.figure()
            ax = fig.subplots(1,1)
            
            x_values = []
            y_values = []
            with open(p["data_path"], "r") as f:
                for line in f:
                    x, y = line.split(" ")
                    x_values.append(float(x))
                    y_values.append(float(y))
                
            ax.plot(x_values, y_values)
            ax.set_xlabel(p["x_label"])
            ax.set_ylabel(p["y_label"])
            fig.tight_layout()
            fig.savefig("{}/{}_{}.png".format(out_path, name, p["type"]))
