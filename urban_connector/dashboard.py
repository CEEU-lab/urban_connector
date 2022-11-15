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

menu_list = st.sidebar.radio('Secciones', ["Start",  "Connectivity", "Accessibility"])

if menu_list == "Start":

    col1, _ ,col3 = st.columns((2,0.5,2))

    col1.header("Urban connector")

    col1.markdown("""
                ```
                > Tools for urban mobility analysis
                ```
    """)

    landing = Image.open('./img/fire_streets.png')
    col3.image(landing, width=550)
    

    st.subheader('**Modeling sections**')
    st.markdown("""
    
    * **Connectivity**:
        ```
        - assess the connectivity level of network streets by providing centrality metrics and shortest path between nodes. 
        ```
    * **Accessibility**:
        ```
        - estimates accessibility to theoric points of interest by calculating travel time isochrones from street network nodes.
        ```
    """)


elif menu_list == "Connectivity":

    st.subheader('Street mobility')
    st.markdown('Select a reference point on the map to generate a street network.')
    st.markdown(' ')

    network_types = ["all_private", "all", "bike", "drive", "drive_service", "walk"]
    connectivity_stats = ['Node degree', 'Degree centrality', 'Betweenness centrality']

    col1, col2, col3, _, col4, col5 = st.columns((0.35, 0.45, 0.5, 0.05, 0.8, 0.75))
    col6, col7 = st.columns(2)

    selected_network_type = col1.selectbox('Network type', network_types, index=5)
    selected_stats = col2.selectbox('Connectivity metric', connectivity_stats, index=0)
    buffer_dist = col3.number_input('DIstance buffer (mts)', min_value=300)

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

    origin = col4.number_input('Origin', value=first_node)
    destin = col5.number_input('Destination', value=last_node)

    route = nx.shortest_path(G, ordinal_idx_to_osmnidx[origin], ordinal_idx_to_osmnidx[destin])

    # shortest path routing
    with col7:
        fig2 = ox.folium.plot_route_folium(G,route, color='red')
        folium_static(fig2, width=625, height=490)

    definitions = {
                   'Node degree':'The degree of a node is the number of edges (streets) connected to the node',
                   'Degree centrality':'''The degree of centrality (or degree centrality) of a node computes the 
                                          number of connections of the node normalized by the total number of nodes within the network. 
                                          Thus, this metric indicates the percentage of current connections over the maximum possible.''',
                   'Betweenness centrality':'''Betweenness centrality is a measure of centrality
                                            which quantifies the number of times a node is between the
                                            shortest paths in the network. A node will have high betweenness if
                                            It is present in a high percentage of them.''',
                   }
    with st.expander("Inspect indicator"):
     st.write('{}'.format(definitions[selected_stats]))

elif menu_list == "Accessibility":
    st.subheader('Street accessibility')
    st.markdown('''Indicate the name place where you want to build a street network and click on
                   the map to get a reference point to which travel times will be calculated
                   for all nodes in the network.''')
    st.markdown(' ')

    col1, col2, col3 = st.columns(3)
    default_place= 'Villa Hidalgo, José León Suárez, Partido de General San Martín, Buenos Aires'
    place = col1.text_input(label='Place your network', value=default_place)

    network_types = ["all_private", "all", "bike", "drive", "drive_service", "walk"]
    selected_network_type = col2.selectbox('Network type', network_types, index=5)
    travel_speed = col3.number_input('Travel speed (km/h)', min_value=4)


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