import branca.colormap as cm
import networkx as nx
import osmnx as ox
import folium
import numpy as np


def build_street_network(category_name, ref, buffer_dist):
    """
    """
    ox.config(log_file=False, log_console=False, use_cache=True)
    G = ox.graph_from_point(center_point=ref, dist=buffer_dist,
                            dist_type='network', network_type=category_name)
    return G

def betweenness_centrality(G, network_type):
    """
    """
    if 'drive' in network_type:
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        D = ox.utils_graph.get_digraph(G, weight="travel_time")

        # calculate node betweenness centrality, weighted by travel time
        bc_wtt = nx.betweenness_centrality(D, weight="travel_time", normalized=True)
        nx.set_node_attributes(G, values=bc_wtt, name="Betweenness centrality")

    elif (network_type == 'bike') or (network_type == 'walk'):
        D = ox.utils_graph.get_digraph(G) # default is "length"

        # calculate node betweenness centrality, weighted by edges length
        bc_wl = nx.betweenness_centrality(D, normalized=True, weight='length')
        nx.set_node_attributes(G, values=bc_wl, name="Betweenness centrality")

    else:
        D = ox.utils_graph.get_digraph(G)
        # calculate betweenness centrality without weight (default is None)
        bc = nx.betweenness_centrality(D, normalized=True)
        nx.set_node_attributes(G, values=bc, name="Betweenness centrality")
    return G

def degree_centrality(G):
    """
    """
    dc = nx.degree_centrality(G)
    nx.set_node_attributes(G, values=dc, name="Degree centrality")
    return G

def node_degree(G):
    """
    """
    nd = dict(G.degree())
    nx.set_node_attributes(G, values=nd, name="Node degree")
    return G

def plot_nodes_folium(G, attr_name, palette, zoom=1, tiles='cartodbpositron', fit_bounds=True, add_legend=True):
    """
    Plot a graph's nodes colored by attribute as an interactive Leaflet web map.
    Parameters
    ----------
    G : networkx.MultiDiGraph
        input graph
    attr_name: string
        name of the nodes attribute
    palette: string
        name of the color palette to color nodes
    zoom : int
        initial zoom level for the map
    tiles : string
        name of a folium tileset
    fit_bounds : bool
        if True, fit the map to the boundaries of the graph's nodes
    add_legend: bool
        if True, colormap legend is added to the map
    Returns
    -------
    folium.folium.Map
    """
    gdf_nodes = ox.graph_to_gdfs(G)[0]

    if attr_name in gdf_nodes.columns:
        node_colors = ox.plot.get_node_colors_by_attr(G, attr_name, cmap=palette)
        gdf_nodes['nc'] = node_colors
    else:
        raise ValueError('To plot {}, this must be added as a graph nodes attribute first'.format(attr_name))

    return _make_folium_circlemarker(gdf_nodes, tiles, zoom, fit_bounds, attr_name, add_legend)

def _make_folium_circlemarker(gdf, tiles, zoom, fit_bounds, attr_name, add_legend):
    """
    Plot a GeoDataFrame of Points on a folium map object.
    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        a GeoDataFrame of Point geometries and attributes
    tiles : string
        name of a folium tileset
    zoom : int
        initial zoom level for the map
    fit_bounds : bool
        if True, fit the map to gdf's boundaries
    attr_name: string
        name of the nodes attribute
    add_legend: bool
        if True, colormap legend is added to the map
    Returns
    -------
    m : folium.folium.Map
    """

    # base layer
    x, y = gdf.unary_union.centroid.xy
    centroid = (y[0], x[0])

    m = folium.Map(location=centroid, zoom_start=zoom, tiles=tiles)

    if fit_bounds:
        tb = gdf.total_bounds
        m.fit_bounds([(tb[1], tb[0]), (tb[3], tb[2])])

    nodes_group = folium.map.FeatureGroup()

    # colormap
    lower_limit = gdf[attr_name].min()
    upper_limit = gdf[attr_name].max()
    node_colors = list(gdf.sort_values(by=attr_name)['nc'].values)
    node_attrs = list(gdf.sort_values(by=attr_name)[attr_name].values)

    colormap = cm.LinearColormap(colors=node_colors, index=node_attrs,
                                 vmin=lower_limit, vmax=upper_limit)

    # map legend
    if add_legend:
        colormap = colormap.to_step(index=np.linspace(lower_limit, upper_limit, num=10))
        colormap.caption = attr_name
        colormap.add_to(m)

    # add nodes to the container individually
    for y, x, idx, node_attr in zip(gdf['y'], gdf['x'], gdf['ordinal_idx'], gdf[attr_name], ):
        nodes_group.add_child(
            folium.vector_layers.CircleMarker(
            [y, x],
            radius= 5,
            color=None,
            fill=True,
            fill_color=colormap.rgba_hex_str(node_attr),
            fill_opacity=0.6,
            tooltip = str(idx)+': ' + str(round(node_attr,2))
            )
        )
    m.add_child(nodes_group)

    return m