import copy
import numpy as np
import pandas as pd
from shapely.geometry import MultiPoint, LineString

import momepy
import networkx as nx
from .calc_tools import *

# create the field node_id in the node gdf, with its mapping id
# create the fields node_start_id and node_end_id in the edges gdf, with mapping ids of the starting and ending point of the each edge
def map_node_ids_in_graph_gdfs(gdf_nodes, gdf_edges, mapping):
    gdf_nodes['node_id'] = 'x'
    gdf_nodes['node_id'] = gdf_nodes['geometry'].map(lambda row: mapping['map_geom'][row][0])
    map_nodes_to_edges = pd.Series(gdf_nodes.node_id.values, index=gdf_nodes.nodeID).to_dict()

    gdf_edges['node_start_id'] = 'x'
    gdf_edges['node_end_id'] = 'x'
    gdf_edges['node_start_id'] = gdf_edges['node_start'].map(lambda row: map_nodes_to_edges[row])
    gdf_edges['node_end_id'] = gdf_edges['node_end'].map(lambda row: map_nodes_to_edges[row])

    return [gdf_nodes, gdf_edges]

# create a dictionary of the nodes in the graph = {id: [node, geometry]} => node in graph (tuple of coords), geometry in shp
def create_nodes_maps(gdf_nodes):
    gdf_nodes['coords'] = gdf_nodes.apply(lambda row: (row.geometry.x, row.geometry.y), axis = 1)
    map_nodes = gdf_nodes.apply(lambda row: [(row.geometry.x, row.geometry.y), row.geometry], axis = 1).to_dict()
    map_coords= gdf_nodes.set_index('coords').T.to_dict('list') 
    map_geom = gdf_nodes.set_index('geometry').T.to_dict('list') 

    return {'map_nodes':map_nodes, 'map_coords':map_coords, 'map_geom':map_geom}

# create a graph from a gdf of linestrings (no multilines)
def create_graph_from_gdf(gdf_network, v_crs_proj, v_directed=False):
    gdf_network = gdf_network.to_crs(v_crs_proj)
    gdf_network['id'] = list(gdf_network.index +1)
    graph = momepy.gdf_to_nx(gdf_network, approach="primal", directed=v_directed)
    nodes, edges, sw = momepy.nx_to_gdf(graph, points=True, lines=True, spatial_weights=True)
    mapping_nodes = create_nodes_maps(nodes)
    nodes, edges = map_node_ids_in_graph_gdfs(nodes, edges, mapping_nodes)
    edges['category'] = 'edge'
    return [gdf_network, graph, nodes, edges, mapping_nodes]

# create a new graph (nodes and edges) from geodata file (shp, geojson, etc)
def create_graph_from_file(v_file_path, v_crs_proj, v_directed=False):
    gdf_network = gpd.read_file(v_file_path)
    gdf_network = gdf_network.to_crs(v_crs_proj)
    gdf_network, graph, nodes, edges, mapping_nodes = create_graph_from_gdf(gdf_network, v_crs_proj, v_directed)
    return [gdf_network, graph, nodes, edges, mapping_nodes]

# create a graph with all the nodes within a limit cost, from a starting node
# create a new graph (subgraph) from an existing graph,starting in a node and using the cost limit  
# returns the subgraph, and it's nodes and edges
def create_subgraph_from_node_and_cost(graph, v_node_id, d_mapping_edges, v_cost_value, f_cost_field):    
    center_node =  list(graph.nodes())[v_node_id]
    subgraph = nx.ego_graph(graph, center_node, radius=v_cost_value, distance=f_cost_field)
    sub_nodes, sub_edges, sw = momepy.nx_to_gdf(subgraph, points=True, lines=True, spatial_weights=True)
    sub_nodes, sub_edges = map_node_ids_in_graph_gdfs(sub_nodes, sub_edges, d_mapping_edges)
    sub_nodes = sub_nodes.loc[sub_nodes.node_id != v_node_id]
    sub_edges.category.fillna('edge', inplace=True)
    return [subgraph, sub_nodes, sub_edges]

#************* INSERT ***************
# insert a location (as node) to a graph, from a point in a gdf (params gdf and id)
# get the nearest edge and conect the location to its nodes
# calculate the weight of the new edges (interpolation)
def insert_location_to_graph(gdf_points, point_id, graph, gdf_nodes, gdf_edges, mapping_nodes, f_weight, v_dist):

    gdf_point = gdf_points.loc[gdf_points.id == point_id]
    
    # update map
    gdf_point_node = (list(gdf_point.geometry)[0].x, list(gdf_point.geometry)[0].y)
    n_map_position = len(mapping_nodes['map_nodes'])
    mapping_nodes['map_nodes'][n_map_position] = [gdf_point_node, list(gdf_point.geometry)[0]]
    mapping_nodes['map_coords'][gdf_point_node] = [n_map_position, list(gdf_point.geometry)[0]]
    mapping_nodes['map_geom'][list(gdf_point.geometry)[0]] = [n_map_position, gdf_point_node]
    
    target_pt_1, target_pt_2, target_w, length_line = nearest_edge_to_point_parameters(gdf_point, gdf_edges, f_weight, v_dist)
    if sum([target_pt_1, target_pt_2, target_w, length_line]) != 0:
        w_1 = calculate_weight_to_node_of_nearest_edge(gdf_point, gdf_nodes, target_pt_1, length_line, target_w)
        w_2 = calculate_weight_to_node_of_nearest_edge(gdf_point, gdf_nodes, target_pt_2, length_line, target_w)

        edges_list = [
            (gdf_point_node, mapping_nodes['map_nodes'][target_pt_1][0], {f_weight: w_1, 'category':'loc', 'geometry':LineString([gdf_point_node, mapping_nodes['map_nodes'][target_pt_1][0]])}),
            (gdf_point_node, mapping_nodes['map_nodes'][target_pt_2][0], {f_weight: w_2, 'category':'loc', 'geometry':LineString([gdf_point_node, mapping_nodes['map_nodes'][target_pt_2][0]])}),
        ]
        
        graph.add_edges_from(edges_list)
        return [graph, mapping_nodes, 1]
    else:
        return [graph, mapping_nodes, 0]

def insert_poly_location_to_graph(gdf_locations, v_loc_id, graph, gdf_nodes, gdf_edges, d_mapping, f_cost, v_dist):
    
    locations_pt = gdf_locations.loc[[v_loc_id]]
    locations_pt.geometry = locations_pt.geometry.apply(lambda x: MultiPoint(list(x.exterior.coords)))
    locations_pt = locations_pt.explode(index_parts=True).reset_index(drop=True)
    locations_pt.id = locations_pt.index + 1
    locations_pt = locations_pt.iloc[:-1]

    v_conected_total = 0
    for i in list(locations_pt.id):
        G_updated, mapping_nodes_updated, v_conected = insert_location_to_graph(locations_pt, i, graph, gdf_nodes, gdf_edges, d_mapping, f_cost, v_dist)
        v_conected_total += v_conected

    # edges between polygon vertex
    list_coords = [(b[0], b[1]) for b in np.dstack(gdf_locations.loc[0, 'geometry'].boundary.coords.xy)[0][:-1]]
    start_node = list_coords[0]
    edges_list = []
    for end_node in list_coords[1:]:
        edges_list.append((start_node, end_node, {f_cost: 0, 'category':'loc', 'geometry':LineString([start_node, end_node])}))
    G_updated.add_edges_from(edges_list)

    return [G_updated, mapping_nodes_updated, v_conected_total]

#************* MODIFY ***************
# change nodes in graph to coords (tuple of coords, as initialy)
def relabel_nodes_to_coords(v_graph, v_mapping):
    mapping_dict = {}
    for n in v_mapping.keys():
        mapping_dict[v_mapping[n][0]] = n
    new_graph = nx.relabel_nodes(v_graph, mapping_dict, copy=True)
    return new_graph

# change nodes in graph to numbers (id)
def relabel_nodes_to_numbers(v_graph, v_mapping):
    mapping_dict = {}
    for n in v_mapping.keys():
        mapping_dict[v_mapping[n][0]] = n
    new_graph = nx.relabel_nodes(v_graph, mapping_dict, copy=True)
    return new_graph