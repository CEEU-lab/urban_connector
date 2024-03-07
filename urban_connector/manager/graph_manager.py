import osmnx as ox
import networkx as nx


# *******************  CREATE GRAPH FROM OSMNX

def osmnx_graph_from_polygon (poly_boundary, network_type='walk', speed=4.5):
    
    poly_geom = poly_boundary.loc[0, "geometry"]
    G = ox.graph.graph_from_polygon(
        polygon= poly_geom, 
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

    return G



# *******************  CREATE GRAPH FROM LINES







