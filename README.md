# bbr2-mininet

Aca hay varias cosas distintas que hicimos con Python para un trabajo final de Trafico:

- En `/informe` esta el informe que explica todo esto y una presentacion.

- En `/tcp-mininet` estan los scripts que usamos para comparar diferentes algoritmos de
    control de congestion de TCP. Especialmente BBRv1 y BBRv2. Estos scripts automatizan
    una prueba que usa mininet, tc, netem, tcpdump, captcp, iperf y qlen_plot.

- `/captcp-mininet` es un fork de [hgn/captcp](https://github.com/hgn/captcp) con algunos
    cambios. Soluciona un problema que no permite interrumpir `captcp socketstatistic &`
    con SIGINT. Tambien se eliminaron algunos mensajes de log que nos molestaban.

- `/qlen_plot` contiene un script Python que almacena en un archivo los tamanos de cola
    haciendo polling a `tc`, sirve para que luego `/tcp-mininet` haga graficos. Es una
    modificacion de codigo propio de Mininet.

- En `/frr-miniedit` hay un clon de miniedit pero con la posibilidad de agregar routers
    FRRouting. Lo que hicimos es reemplazar el router original por uno que ejecuta
    FRRouting. Esto no esta muy relacionado al resto de cosas en este repositorio.

Las licencias son MIT salvo que el archivo diga otra cosa (porque hay codigo sacado de
varios lados)
