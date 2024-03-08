import osmnx as ox
import networkx as nx
import momepy

# *******************  CREATE GRAPH FROM OSMNX

def osmnx_graph_from_polygon (poly_boundary, network_type='walk', speed=4.5):
    
    G = ox.graph.graph_from_polygon(
        polygon= poly_boundary, 
        network_type=network_type
    )

    speed_m_min = speed * 1000 / 60
    w_dict = nx.get_edge_attributes(G, 'length')
    w_dict.update([(x, y / speed_m_min) for x, y in w_dict.items() ])
    nx.set_edge_attributes(G, w_dict, "weight")

    x_dict = nx.get_node_attributes(G, 'x')
    y_dict = nx.get_node_attributes(G, 'y')
    x_dict.update([(x, (y, y_dict[x])) for x, y in x_dict.items() ])
    nx.set_node_attributes(G, x_dict, "coords")

    new_nodes_names = {node:'n_'+str(node) for node in list(G.nodes)}
    G = nx.relabel_nodes(G, new_nodes_names, copy=False)

    return G

# *******************  CREATE GRAPH FROM LINES

# create a graph from a gdf of linestrings (no multilines)
def create_graph_from_gdf(gdf_network, v_make_directed=False, v_directed=False, remove_isolated=False, remove_selfloop=False):

    if 'label' in list(gdf_network.columns):
        graph = momepy.gdf_to_nx(gdf_network[['id', 'weight', 'label', 'geometry']], approach="primal", directed=v_directed)
    else:
        graph = momepy.gdf_to_nx(gdf_network[['id', 'weight', 'geometry']], approach="primal", directed=v_directed)

    if remove_isolated == True:
        graph.remove_nodes_from(list(nx.isolates(graph)))
    if remove_selfloop == True:
        graph.remove_edges_from(nx.selfloop_edges(graph))

    if v_make_directed == True:
        graph = graph.to_directed(as_view=False)

    graph_2 = nx.convert_node_labels_to_integers(graph, first_label=0, ordering='default', label_attribute='coords')
    if 'label' in list(gdf_network.columns):
        v_label = list(gdf_network.label.unique())[0]
        dictionary = dict(zip( list(graph_2.nodes) , [str(x) +"_"+ v_label for x in list(graph_2.nodes)]))
        graph_2 = nx.relabel_nodes(graph_2, dictionary, copy=True)

    attrs_g = {'crs': gdf_network.crs}
    graph_2.graph.update(attrs_g)

    return graph_2





