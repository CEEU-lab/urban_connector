from PIL import Image
import orca
import streamlit as st
from streamlit_folium import st_folium
from streamlit_folium import folium_static
import pandas as pd
import geopandas as gpd

from mobility import *
from accessibility import *
#from datasources import *


st.set_page_config(
    page_title="Urban Connector",
    page_icon="./sl//favicon.ico",
    layout='wide',
    initial_sidebar_state='collapsed')

st.write(
        """
<iframe src="resources/sidebar-closer.html" height=0 width=0>
</iframe>""",
        unsafe_allow_html=True,
    )

# CSS
with open('./sl/style.css') as f:
    st.markdown('<style>{}</style>'.format(f.read()), unsafe_allow_html=True)

menu_list = st.sidebar.radio('Secciones', ["Inicio",  "Mobilidad urbana", "Accesibilidad"])

if menu_list == "Inicio":

    col1, _ ,col3 = st.columns((2,0.5,2))

    col1.header("Urban connector")

    col1.markdown("""
                ```
                > Le corbusier - calles son las venas del tejido urbano.
                ```
    """)

    landing = Image.open('./img/fire_streets.png')
    col3.image(landing, width=550)
    

    st.subheader('**Componentes de análisis**')
    st.markdown("""
    
    * **Mobilidad urbana**:
        ```
        - esta seccion permite estudiar el nivel de conectividad de una red de calles. Esto, mediante la construccion de distintas
          metricas de centralidad y de la identificacion de los caminos mas cortos entre los nodos de la red.
        ```
    * **Accesibilidad**:
        ```
        - esta seccion permite construir una red de calles y evaluar el grado de accesibilidad a cada punto de la misma a
          partir de la construccion de isocronas con el tiempo de viaje desde cada uno de sus nodos.
        ```
    """)


elif menu_list == "Mobilidad urbana":

    st.subheader('Visor de mobilidad')
    st.markdown('Seleccione un punto de referencia sobre el mapa para generar una red de calles.')
    st.markdown(' ')

    network_types = ["all_private", "all", "bike", "drive", "drive_service", "walk"]
    connectivity_stats = ['Node degree', 'Degree centrality', 'Betweenness centrality']

    col1, col2, col3, _, col4, col5 = st.columns((0.35, 0.45, 0.5, 0.05, 0.8, 0.75))
    col6, col7 = st.columns(2)

    selected_network_type = col1.selectbox('Tipo de red', network_types, index=5)
    selected_stats = col2.selectbox('Métrica de conectividad', connectivity_stats, index=0)
    buffer_dist = col3.number_input('Indique buffer de distancia (mts)', min_value=300)

    if 'ref' in orca.list_injectables():
        ref = orca.get_injectable('ref')
    else:
        # use a default reference point
        ref = (-34.50944, -58.58610)

    G = build_street_network(selected_network_type, ref, buffer_dist)

    if selected_stats == 'Node degree':
        network_metric = node_degree(G)
    elif selected_stats == 'Degree centrality':
        network_metric = degree_centrality(G)
    elif selected_stats == 'Betweenness centrality':
            network_metric = betweenness_centrality(G, selected_network_type)
    else:
        print('Add other supported network stats')

    colors = {'Betweenness centrality':'plasma',
              'Degree centrality':'viridis',
              'Node degree':'YlOrRd'}

    # set ordinal idx for shortest path routing nodes recognition
    counter = 1
    for n in G.nodes(data=True):
        n[1]['ordinal_idx'] = counter
        counter += 1

    # node attributes
    fig1 = plot_nodes_folium(G, attr_name=selected_stats, palette=colors[selected_stats])
    fig1.add_child(folium.LatLngPopup())

    with col6:
        mapdata = st_folium(fig1, width=625, height=500)

    if mapdata is not None:
        print(mapdata['last_clicked'])
        # interacts with the map and generates new reference
        if mapdata['last_clicked'] is not None:
            lat_click = mapdata['last_clicked']['lat']
            lng_click = mapdata['last_clicked']['lng']
            ref = (lat_click, lng_click)
            orca.add_injectable('ref', ref)
        else:
            informative_print = ''
            st.write(informative_print)

    # map ordinal idx to osmn id
    ordinal_idx_to_osmnidx = {}
    for n in G.nodes(data=True):
        ordinal_idx_to_osmnidx[n[1]['ordinal_idx']] = n[0]

    first_node = list(ordinal_idx_to_osmnidx.keys())[0]
    last_node = list(ordinal_idx_to_osmnidx.keys())[-1]

    origin = col4.number_input('Origen', value=first_node)
    destin = col5.number_input('Destino', value=last_node)

    route = nx.shortest_path(G, ordinal_idx_to_osmnidx[origin], ordinal_idx_to_osmnidx[destin])

    # shortest path routing
    with col7:
        fig2 = ox.folium.plot_route_folium(G,route, color='red')
        folium_static(fig2, width=625, height=490)

    definitions = {
                   'Node degree':'El grado de un nodo indica la cantidad de ejes o calles adyacentes al nodo.',
                   'Degree centrality':'''El grado de centralidad (o degree centrality) de un nodo computa la cantidad
                                        de conexiones del nodo normalizada por el total de nodos dentro de la red. Así,
                                        dicha métrica indica el porcentage de conexiones actual sobre el máximo posible.''',
                   'Betweenness centrality':'''La centralidad de intermediación, o simplemente intermediación
                                            (en inglés, betweenness) es una medida de centralidad
                                            que cuantifica el número de veces que un nodo se encuentra entre los
                                            caminos más cortos de la red. Un nodo tendrá una alta intermediación si
                                            se encuentra presente en un elevedado porcentage de los mismos.''',
                   }
    with st.expander("Inspeccionar indicador"):
     st.write('{}'.format(definitions[selected_stats]))

elif menu_list == "Accesibilidad":
    st.subheader('Visor de accesibilidad')
    st.markdown('''Indique el lugar donde desea construir una red de calles y cliquee sobre
                   el mapa para obtener un punto de referencia al que se calcularán los tiempos de viaje
                   para todos los nodos de la red.''')
    st.markdown(' ')

    col1, col2, col3 = st.columns(3)
    default_place= 'Villa Hidalgo, José León Suárez, Partido de General San Martín, Buenos Aires'
    place = col1.text_input(label='Ingresar nombre del sitio', value=default_place)

    network_types = ["all_private", "all", "bike", "drive", "drive_service", "walk"]
    selected_network_type = col2.selectbox('Tipo de red', network_types, index=5)
    travel_speed = col3.number_input('Indique la velocidad de viaje (en km/h)', min_value=4)


    G = build_graph_by_name(place, network_type=selected_network_type)
    kwargs = {'weight' : '0.75', 'color': 'grey'}
    fig1 = ox.plot_graph_folium(G, tiles='openstreetmap',  **kwargs)
    fig1.add_child(folium.LatLngPopup())

    # nodes
    fig2 = plot_simple_nodes_folium(G, m=fig1, node_color='red')

    col4, col5 = st.columns(2)

    with col4:
        mapdata = st_folium(fig1, width=625, height=500)

    if mapdata is not None:
        print(mapdata['last_clicked'])
        # interacts with the map and generates new reference
        if mapdata['last_clicked'] is not None:
            lat_click = mapdata['last_clicked']['lat']
            lng_click = mapdata['last_clicked']['lng']
            ref = (lat_click, lng_click)

            with col5:
                fig3 = ox.plot_graph_folium(G, tiles='cartodbdark_matter',  **kwargs)
                fig4 = plot_isochrone(G, ref, travel_speed, m=fig3)
                slat = mapdata['bounds']['_southWest']['lat']
                slon = mapdata['bounds']['_southWest']['lng']
                nlat = mapdata['bounds']['_northEast']['lat']
                nlon = mapdata['bounds']['_northEast']['lng']
                fig4.fit_bounds([(slat, slon), (nlat, nlon)])
                folium_static(fig4, width=625, height=490)