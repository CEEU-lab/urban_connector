import osmnx as ox
import folium
import networkx as nx
import branca.colormap as cm
import numpy as np

def build_graph_by_name(place, network_type):
    ox.config(log_file=False, log_console=False, use_cache=False)
    G = ox.graph_from_address(place,network_type=network_type)
    return G

def plot_simple_nodes_folium(G, m, node_color='blue'):
    '''
    Doesn't color nodes by attribute. This generates
    folium.Map objectto optionally add it to LineStrings (edges)
    '''
    gdf_nodes = ox.graph_to_gdfs(G)[0]
    x, y = gdf_nodes.unary_union.centroid.xy
    centroid = (y[0], x[0])

    nodes_group = folium.map.FeatureGroup()

    # add nodes to the container individually
    for y, x in zip(gdf_nodes['y'], gdf_nodes['x'], ):
        nodes_group.add_child(
            folium.vector_layers.CircleMarker(
            [y, x],
            radius= 3,
            color=None,
            fill=True,
            fill_color=node_color,
            fill_opacity=0.6,
            tooltip = None
            )
        )
    m.add_child(nodes_group)

    return m

def plot_isochrone(G, ref, travel_speed, m):

    # Use the more efficient `distance.nearest_nodes` instead.
    #center_node = ox.get_nearest_node(G,ref)
    center_node = ox.nearest_nodes(G,X=ref[1],Y=ref[0])
    #center_node = ox.distance.nearest_nodes(G,X=ref[0], Y=ref[1])

    meters_per_minute = travel_speed * 1000 / 60
    for u, v, k, data in G.edges(data=True, keys=True):
        data['time'] = data['length'] / meters_per_minute

    trip_times = [5,10,15,25] # in minutes

    # get one color for each isochrone
    iso_colors = ox.plot.get_colors(n=len(trip_times), cmap='plasma', start=0, return_hex=True)
    node_colors = {}
    node_times = {}
    for trip_time, color in zip(sorted(trip_times, reverse=True), iso_colors):
        subgraph = nx.ego_graph(G, center_node, radius=trip_time,  distance='time')
        for node in subgraph.nodes():
            node_colors[node] = color
            node_times[node] = trip_time
    nc = [node_colors[node] if node in node_colors else 'none' for node in G.nodes()]
    #ns = [15 if node in node_colors else 0 for node in G.nodes()]
    nt = [node_times[node] if node in node_times else 'none' for node in G.nodes()]
    ns = {5:10, 10:9, 15:8, 25:7}

    # plot graph
    gdf_nodes = ox.graph_to_gdfs(G)[0]
    gdf_nodes['nc'] = nc
    gdf_nodes['nt'] = nt
    gdf_nodes['ns'] = gdf_nodes['nt'].map(ns)

    nodes_group = folium.map.FeatureGroup()


    # add nodes to the container individually
    for y, x, nt, nc, ns in zip(gdf_nodes['y'], gdf_nodes['x'], gdf_nodes['nt'], gdf_nodes['nc'], gdf_nodes['ns'], ):
        nodes_group.add_child(
            folium.vector_layers.CircleMarker(
            [y, x],
            radius= ns,
            color=None,
            fill=True,
            fill_color=nc,
            fill_opacity=0.6,
            tooltip = 'Tiempo de viaje: '+ str(nt) + 'minutos'
            )
        )
    m.add_child(nodes_group)
    return m