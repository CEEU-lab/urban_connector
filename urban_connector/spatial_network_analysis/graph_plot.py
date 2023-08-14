import networkx as nx
import matplotlib.pyplot as plt
from .graph_manager import relabel_nodes_to_numbers

# plot three graphics: network, graph, network+graph
def plot_geo_graph(v_gdf, v_graph, v_node_mapping):
    f, ax = plt.subplots(1, 3, figsize=(18, 6), sharex=True, sharey=True)
    v_gdf.plot(color='#e32e00', ax=ax[0])
    for i, facet in enumerate(ax):
        facet.set_title(("Streets", "Primal graph", "Overlay")[i])
        facet.axis("off")
    nx.draw(v_graph, {v_node_mapping[n][0]:[v_node_mapping[n][0][0], v_node_mapping[n][0][1]] for n in v_node_mapping.keys()}, ax=ax[1], node_size=15)
    v_gdf.plot(color='#e32e00', ax=ax[2], zorder=-1)
    nx.draw(v_graph, {v_node_mapping[n][0]:[v_node_mapping[n][0][0], v_node_mapping[n][0][1]] for n in v_node_mapping.keys()}, ax=ax[2], node_size=15)

# plot graph with node ids
def plot_graph (v_graph, v_mapping):
    new_graph = relabel_nodes_to_numbers(v_graph, v_mapping)
    nx.draw_spring(new_graph, with_labels=True)
    plt.show()