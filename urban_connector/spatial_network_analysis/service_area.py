from shapely.geometry import Point, LineString, Polygon
import networkx as nx
import momepy
import pandas as pd
import geopandas as gpd
from .graph_manager import create_subgraph_from_node_and_cost, insert_location_to_graph, insert_poly_location_to_graph
import os
import copy

# given a limit cost, calculate the remaining cost left to go, as the difference of the sum of cost from the starting point to the actual node
""" def calc_remaining_weight(graph, v_node_id, v_node_id_target, d_mapping_edges, v_cost_value, f_cost_field):
    cost_value_sum = nx.shortest_path_length(graph, source=d_mapping_edges['map_nodes'][v_node_id][0], target=d_mapping_edges['map_nodes'][v_node_id_target][0], weight=f_cost_field)
    v_cost_value_remainnig = v_cost_value - cost_value_sum
    return v_cost_value_remainnig """

# calculate
def calc_sum_of_cost_to_edge_endnode(subgraph, v_node_id, gdf_subnodes, gdf_subedges, d_mapping, f_cost_field, v_cost):
    cost_map = nx.shortest_path_length(subgraph, source=d_mapping['map_nodes'][v_node_id][0], weight=f_cost_field)
    gdf_subedges['cost_sum'] = gdf_subedges['node_end_id'].map(lambda row: cost_map[d_mapping['map_nodes'][row][0]])
    gdf_subnodes['cost_sum'] = gdf_subnodes['node_id'].map(lambda row: cost_map[d_mapping['map_nodes'][row][0]])
    gdf_subnodes['cost_rem'] = v_cost - gdf_subnodes['node_id'].map(lambda row: cost_map[d_mapping['map_nodes'][row][0]])
    return [gdf_subnodes, gdf_subedges]

# get a list of all the nodes conecting to the input node, and a list of the weights to the edges to this nodes
def get_adjacent_nodes_id_and_weight(gdf_edges, v_node_id_target, f_cost_field):
    l_near_nodes = list(gdf_edges.loc[gdf_edges.node_start == v_node_id_target, 'node_end']) + list(gdf_edges.loc[gdf_edges.node_end == v_node_id_target, 'node_start'])
    l_near_nodes_w = list(gdf_edges.loc[gdf_edges.node_start == v_node_id_target, f_cost_field]) + list(gdf_edges.loc[gdf_edges.node_end == v_node_id_target, f_cost_field])
    return [l_near_nodes, l_near_nodes_w]

# remove duplicated edges by start and end point
def remove_duplicated_edges(gdf_edge):
    gdf_edge = gdf_edge.loc[gdf_edge.geometry.notnull()]

    gdf_edge.loc[gdf_edge.category == 'edge', 'swap'] = gdf_edge.loc[gdf_edge.category == 'edge', ['node_start_id', 'node_end_id']].apply(lambda row : 1 if row.node_end_id < row.node_start_id else 0, axis=1)
    gdf_edge.swap.fillna(0, inplace=True)
    gdf_edge[['node_start_id','node_end_id']] = gdf_edge[['node_end_id','node_start_id']].where(gdf_edge['swap'] == 1, gdf_edge[['node_start_id','node_end_id']].values)

    gdf_edge['length'] = gdf_edge.length
    gdf_edge = gdf_edge.sort_values(by=['cost_limit', 'cost_sum', 'length'], ascending=[True, True, False]).reset_index(drop=True)
    gdf_edge = gdf_edge.drop_duplicates(subset=['node_start_id', 'node_end_id'])

    return gdf_edge

# remove semiedges overlaping edges
def remove_semiedges_overlaping_edges(gdf_edge):
    gdf_edge_structure = gpd.GeoDataFrame([], columns=['category', 'origin_id_point', 'node_start_id', 'node_end_id', 'cost_sum', 'cost_limit', 'geometry'], geometry='geometry')

    a_main = gdf_edge.loc[gdf_edge.category == 'edge'].reset_index(drop=True)
    a_semi = gdf_edge.loc[gdf_edge.category == 'semi'].reset_index(drop=True)
    a_loc = gdf_edge.loc[gdf_edge.category == 'loc'].reset_index(drop=True)

    gdf_edge_structure = pd.concat([gdf_edge_structure, a_main, a_loc])

    """ list_tuples_nodes = a_main.apply(lambda row: (row.node_start_id, row.node_end_id), axis=1).to_list() + a_main.apply(lambda row: (row.node_end_id, row.node_start_id), axis=1).to_list()
    a_semi = a_semi.loc[a_semi.apply(lambda row: (row.node_start_id, row.node_end_id) not in list_tuples_nodes, axis=1)]

    gdf_edge_structure = pd.concat([gdf_edge_structure, a_semi]) """

    list_tuples_nodes = []
    for i in list(a_main.index):
        v_start_node = a_main.loc[i, "node_start_id"]
        v_end_node = a_main.loc[i, "node_end_id"]
        list_tuples_nodes += [(v_start_node, v_end_node), (v_end_node, v_start_node)]

    for i in list(a_semi.index):
        v_start_node = a_semi.loc[i, "node_start_id"]
        v_end_node = a_semi.loc[i, "node_end_id"]
        node_tuple = (v_start_node, v_end_node)

        if node_tuple not in list_tuples_nodes:
            gdf_edge_structure = pd.concat([gdf_edge_structure, a_semi.loc[[i]]])

    return gdf_edge_structure


#----------------------------------------------------------------------------------
# creates lines from one node to another, but only a percentage of it
# MAYBE ITS BETTER TO SPLIT THE EDGE BY THE POINT AND NOT CREATING ANOTHER LINE - to develop
def create_semiedge_from_node_by_cost_over_edge(t_point_start, t_point_destiny, v_cost_perc):
    v_point_middle_x = LineString([t_point_start, t_point_destiny]).interpolate(v_cost_perc, normalized=True).x
    v_point_middle_y = LineString([t_point_start, t_point_destiny]).interpolate(v_cost_perc, normalized=True).y
    t_point_middle = (v_point_middle_x, v_point_middle_y)
    linestring_new = LineString([t_point_start, t_point_middle])
    return linestring_new

# given a gdf of edges, add a new edge to the gdf
def add_new_semiedge_to_subedges(v_node_position, v_mapping, gdf_subedges, v_node_id, t_point_start, l_near_nodes, l_near_nodes_w, v_cost_value_remainnig):
    v_id = l_near_nodes[v_node_position]
    v_weight = l_near_nodes_w[v_node_position]
    t_point_destiny = v_mapping['map_nodes'][v_id][0] # (list(gdf_nodes.loc[gdf_nodes.node_id == v_id, 'geometry'].x)[0], list(gdf_nodes.loc[gdf_nodes.node_id == v_id, 'geometry'].y)[0])

    if v_weight != 0:
        v_cost_perc = v_cost_value_remainnig / v_weight

        if v_cost_perc < 1 :
            g_line_semiedge = create_semiedge_from_node_by_cost_over_edge(t_point_start, t_point_destiny, v_cost_perc)
            
            v_gdf_new_id = len(gdf_subedges)
            gdf_subedges.loc[v_gdf_new_id] = gdf_subedges.loc[0]
            gdf_subedges.loc[v_gdf_new_id, 'category'] = 'semi'
            gdf_subedges.loc[v_gdf_new_id, 'node_start_id'] = v_node_id
            gdf_subedges.loc[v_gdf_new_id, 'node_end_id'] = v_id
            gdf_subedges.loc[v_gdf_new_id, 'geometry'] = g_line_semiedge

    return gdf_subedges

# calculate the remaining cost to a node and create the part of the edges that still is reachable
"""def create_new_semiedges(graph, gdf_nodes, gdf_edges, v_mapping, gdf_subedges, v_node_id, v_node_id_target, v_cost_value, f_cost_field):

     v_cost_value_remainnig = calc_remaining_weight(graph, v_node_id, v_node_id_target, v_mapping, v_cost_value, f_cost_field) 

    t_point_start = v_mapping['map_nodes'][v_node_id_target][0] # (list(gdf_nodes.loc[gdf_nodes.node_id == v_node_id_target, 'geometry'].x)[0], list(gdf_nodes.loc[gdf_nodes.node_id == v_node_id_target, 'geometry'].y)[0])
    l_near_nodes, l_near_nodes_w = get_adjacent_nodes_id_and_weight(gdf_edges, v_node_id_target, f_cost_field)
    
    [add_new_semiedge_to_subedges(n, v_mapping, gdf_subedges, v_node_id_target, t_point_start, l_near_nodes, l_near_nodes_w, v_cost_value_remainnig) for n in range(len(l_near_nodes))]"""

def create_new_semiedges (graph, v_mapping, gdf_subnodes, gdf_subedges, f_cost_field):
    node_x = list(gdf_subnodes['node_id'].map(lambda row: v_mapping['map_nodes'][row][0]))
    l_adjacent_edges = list(graph.edges(node_x, data=f_cost_field))
    df_adjacent_edges = pd.DataFrame(l_adjacent_edges, columns=['pt_start', 'pt_end', 'w'])
    df_adjacent_edges['node_id'] = df_adjacent_edges['pt_start'].map(lambda row: v_mapping['map_coords'][row][0])
    df_adjacent_edges['node_id_to'] = df_adjacent_edges['pt_end'].map(lambda row: v_mapping['map_coords'][row][0])
    df_adjacent_edges = df_adjacent_edges.merge(gdf_subnodes[['node_id', 'cost_rem']], on='node_id')
    df_adjacent_edges = df_adjacent_edges[['node_id','pt_start', 'node_id_to', 'pt_end', 'w', 'cost_rem']]
    df_adjacent_edges = df_adjacent_edges.loc[df_adjacent_edges.w != 0].reset_index(drop=True)
    df_adjacent_edges['cost_rem_perc'] = df_adjacent_edges['cost_rem'] / df_adjacent_edges['w']
    df_adjacent_edges = df_adjacent_edges.loc[df_adjacent_edges.cost_rem_perc <= 1].reset_index(drop=True)
    df_adjacent_edges['geometry'] = df_adjacent_edges.apply(lambda row:                                                             create_semiedge_from_node_by_cost_over_edge(row.pt_start, row.pt_end, row.cost_rem_perc), axis=1)
    # LineString([row.pt_start, row.pt_end]).interpolate(row.cost_rem_perc, normalized=True)
    
    df_adjacent_edges['category'] = 'semi'
    df_adjacent_edges.rename(columns={'node_id':'node_start_id', 'node_id_to':'node_end_id'}, inplace=True)

    gdf_subedges_with_semiedges = pd.concat([gdf_subedges, df_adjacent_edges[['node_start_id', 'node_end_id', 'category', 'geometry']]])

    return gdf_subedges_with_semiedges
#----------------------------------------------------------------------------------


# create a polygon from the edges in the gdf
""" def create_polygon_surrounding_edges(gdf_edges, gdf_sub_edges, v_buffer_meters, v_dissolve_distance, v_cost_limit):
    
    
    gdf_limite = gdf_sub_edges
    v_dissolve_distance_retract = (-0.99) * v_dissolve_distance
    v_buffer_meters = v_buffer_meters - v_dissolve_distance *0.01

    gdf_limite.geometry = gdf_limite.buffer(v_dissolve_distance) # , join_style=2
    gdf_limite['dis'] = 'xx'
    gdf_limite = gdf_limite.dissolve(by='dis')

    gdf_polygon_sorrounding = Polygon(gdf_limite.boundary.geometry.explode(index_parts=True)[0])
    gdf_limite.geometry[0] = gdf_polygon_sorrounding
    gdf_limite.geometry = gdf_limite.buffer(v_dissolve_distance_retract) # , join_style=2

    gdf_limite.geometry = gdf_limite.buffer(v_buffer_meters) # , join_style=2

    gdf_limite['cost_limit'] = v_cost_limit
    gdf_limite = gdf_limite[['cost_limit', 'geometry']]

    return gdf_limite """

#----------------------------------------------------------------------------------

# create a service area from a node and a list of cost limit
def create_service_edges_from_node(cost_limit, f_cost_field, graph, gdf_edges, d_mapping, v_origen_node_id, v_origin_point_id):
    subgraph, sub_nodes, sub_edges = create_subgraph_from_node_and_cost(graph, v_origen_node_id, d_mapping, cost_limit, f_cost_field)
    sub_nodes, sub_edges = calc_sum_of_cost_to_edge_endnode(graph, v_origen_node_id, sub_nodes, sub_edges, d_mapping, f_cost_field, cost_limit)

    gdf_service_area_edges = create_new_semiedges (graph, d_mapping, sub_nodes, sub_edges, f_cost_field)
    gdf_service_area_edges = gdf_service_area_edges.set_crs(gdf_edges.crs)
    gdf_service_area_edges = remove_semiedges_overlaping_edges(gdf_service_area_edges)

    gdf_service_area_edges['cost_limit'] = cost_limit
    gdf_service_area_edges['origin_id_point'] = v_origin_point_id
    gdf_service_area_edges = gdf_service_area_edges[['category', 'origin_id_point', 'cost_sum', 'cost_limit', 'node_start_id', 'node_end_id', 'geometry']]
    gdf_service_area_edges.cost_sum.fillna(cost_limit, inplace=True)

    return gdf_service_area_edges

def create_polygon_surrounding_edges(gdf_sub_edges, v_start_node_id, v_buffer_meters, v_dissolve_distance):
    v_dissolve_distance_retract = (-0.99) * v_dissolve_distance
    v_buffer_meters = v_buffer_meters - v_dissolve_distance *0.01

    gdf_limite = gdf_sub_edges.copy()
    gdf_limite.geometry = gdf_sub_edges.buffer(v_dissolve_distance, cap_style=2)
    gdf_limite = gdf_limite.dissolve(by='cost_limit').reset_index()
    # gdf_limite = gdf_limite.explode(index_parts=True)
    # gdf_limite.reset_index(drop=True, inplace=True)

    """ for p in gdf_limite.index.to_list():
        gdf_polygon_sorrounding = Polygon(gdf_limite.loc[[p]].boundary.geometry.explode(index_parts=True).to_list()[0])
        gdf_limite.loc[p, 'geometry'] = gdf_polygon_sorrounding """

    gdf_limite.geometry = gdf_limite.buffer(v_dissolve_distance_retract, cap_style=2)
    gdf_limite.geometry = gdf_limite.buffer(v_buffer_meters)

    gdf_limite['origin_id_point'] = v_start_node_id
    gdf_limite = gdf_limite[['origin_id_point', 'cost_limit', 'geometry']]
    return gdf_limite

#----------------------------------------------------------------------------------


""" def create_service_area_from_node(cost_limit, f_cost_field, graph, gdf_edges, v_mapping, v_origen_node_id, v_origin_point_id, v_buffer_meters, v_dissolve_distance):
    
    gdf_all_service_areas = gpd.GeoDataFrame([], columns=['origin_id_point', 'cost_limit', 'geometry'], geometry='geometry')
    gdf_all_service_areas_edges = gpd.GeoDataFrame([], columns=['category', 'origin_id_point', 'cost_sum', 'cost_limit', 'node_start_id', 'node_end_id', 'geometry'], geometry='geometry')
    
    gdf_service_area_edges = create_service_edges_from_node(cost_limit, f_cost_field, graph, gdf_edges, v_mapping, v_origen_node_id, v_origin_point_id)
    gdf_service_area = create_polygon_surrounding_edges(gdf_service_area_edges, v_buffer_meters, v_dissolve_distance)
    gdf_all_service_areas = pd.concat([gdf_all_service_areas, gdf_service_area])
    gdf_all_service_areas_edges = pd.concat([gdf_all_service_areas_edges, gdf_service_area_edges])

    return [gdf_all_service_areas, gdf_all_service_areas_edges] """

# create a multiple service areas from a multiple starting nodes
def create_service_area_from_node_for_multi_costs(l_cost_list, f_cost_field, graph, gdf_edges, v_mapping, v_origen_node_id, v_origin_point_id, v_buffer_meters, v_dissolve_distance):
    
    gdf_all_service_areas = gpd.GeoDataFrame([], columns=['origin_id_point', 'cost_limit', 'geometry'], geometry='geometry')
    gdf_all_service_areas_edges = gpd.GeoDataFrame([], columns=['category', 'origin_id_point', 'cost_sum', 'cost_limit', 'node_start_id', 'node_end_id', 'geometry'], geometry='geometry')
    
    for cost_limit in l_cost_list:
            gdf_service_area_edges = create_service_edges_from_node(cost_limit, f_cost_field, graph, gdf_edges, v_mapping, v_origen_node_id, v_origin_point_id)
            gdf_all_service_areas_edges = pd.concat([gdf_all_service_areas_edges, gdf_service_area_edges])
    
    gdf_service_area = create_polygon_surrounding_edges(gdf_all_service_areas_edges, v_origin_point_id, v_buffer_meters, v_dissolve_distance)
    gdf_all_service_areas = pd.concat([gdf_all_service_areas, gdf_service_area])
        
    gdf_all_service_areas_edges = remove_semiedges_overlaping_edges(gdf_all_service_areas_edges)
    gdf_all_service_areas_edges = remove_duplicated_edges(gdf_all_service_areas_edges)

    return [gdf_all_service_areas, gdf_all_service_areas_edges] 
    # return gdf_all_service_areas_edges

def create_service_areas_for_locations(gdf_locations, v_loc_type, graph, gdf_nodes, gdf_edges, v_mapping_nodes, l_costs, cost_field, v_max_dist, v_buffer_meters, v_dissolve_distance):

    gpd_all_service_areas = gpd.GeoDataFrame([], columns=['origin_id_point', 'cost_limit', 'geometry'], geometry='geometry')
    gdf_all_service_areas_edges = gpd.GeoDataFrame([], columns=['category', 'origin_id_point', 'node_start_id', 'node_end_id', 'cost_sum', 'cost_limit', 'geometry'], geometry='geometry')

    for origin_point_id in list(gdf_locations.id):

        G_original = graph.copy()
        mapping_original = copy.deepcopy(v_mapping_nodes) 
        # G_original = nx.MultiGraph()
        # G_original = nx.compose(G_original, graph)

        if v_loc_type == 'point':
            G_updated, mapping_nodes_updated, v_conected = insert_location_to_graph(gdf_locations, origin_point_id, G_original, gdf_nodes, gdf_edges, mapping_original, cost_field, v_max_dist)
        elif v_loc_type == 'polygon':
            gdf_locations_poly = gdf_locations.loc[gdf_locations.id == origin_point_id]
            gdf_locations_poly.reset_index(drop=True, inplace=True)
            G_updated, mapping_nodes_updated, v_conected = insert_poly_location_to_graph(gdf_locations_poly, 0, G_original, gdf_nodes, gdf_edges, mapping_original, cost_field, v_max_dist)

        if v_conected != 0:
            origen_node_id = len(G_updated.nodes) - 1

            try:
                gdf_service_area, gdf_service_area_edges = create_service_area_from_node_for_multi_costs(l_costs, cost_field, G_updated, gdf_edges, mapping_nodes_updated, origen_node_id, origin_point_id,v_buffer_meters, v_dissolve_distance)

                gpd_all_service_areas = pd.concat([gpd_all_service_areas, gdf_service_area])
                gdf_all_service_areas_edges = pd.concat([gdf_all_service_areas_edges, gdf_service_area_edges])
            
            except:
                print(f'error in location id {origin_point_id} - CHECK PROCESS')
        else:
            print(f"Location id {origin_point_id} not connected to network (d>{v_max_dist})")

    gdf_all_service_areas_edges = remove_semiedges_overlaping_edges(gdf_all_service_areas_edges)
    gdf_all_service_areas_edges = remove_duplicated_edges(gdf_all_service_areas_edges)
                                                          
    gdf_all_service_areas_edges_locs = gdf_all_service_areas_edges.loc[gdf_all_service_areas_edges.category == 'loc'].reset_index(drop=True)
    gdf_all_service_areas_edges = gdf_all_service_areas_edges.loc[gdf_all_service_areas_edges.category != 'loc'].reset_index(drop=True)

    return [gdf_all_service_areas_edges, gdf_all_service_areas_edges_locs, gpd_all_service_areas]



""" def create_polygon_surrounding_edges(gdf_sub_edges, v_buffer_meters, v_dissolve_distance):
    v_dissolve_distance_retract = (-0.99) * v_dissolve_distance
    v_buffer_meters = v_buffer_meters - v_dissolve_distance *0.01

    gdf_limite = gdf_sub_edges
    gdf_limite.geometry = gdf_sub_edges.buffer(v_dissolve_distance)
    gdf_limite = gdf_limite.dissolve(by='cost_limit').reset_index()
    gdf_limite = gdf_limite.explode(index_parts=True)
    gdf_limite.reset_index(drop=True, inplace=True)

    for p in gdf_limite.index.to_list():
        gdf_polygon_sorrounding = Polygon(gdf_limite.loc[[p]].boundary.geometry.explode(index_parts=True).to_list()[0])
        gdf_limite.loc[p, 'geometry'] = gdf_polygon_sorrounding

    gdf_limite.geometry = gdf_limite.buffer(v_dissolve_distance_retract)
    gdf_limite.geometry = gdf_limite.buffer(v_buffer_meters)

    gdf_limite = gdf_limite[['cost_limit', 'geometry']]
    return gdf_limite """

# dissolve service areas into polygons or rings by limit cost
def dissolve_service_areas_polygons( gpd_all_areas, v_type='rings'):

    gpd_all_areas_dis = gpd_all_areas.dissolve(by='cost_limit').reset_index()
    l_cost_list = list(gpd_all_areas_dis.reset_index()['cost_limit'].sort_values(ascending=False))

    if v_type == 'rings':
        gpd_service_areas_result = gpd.GeoDataFrame([], columns=['cost_limit', 'geometry'], geometry='geometry')

        for i in range(len(l_cost_list)-1):
            p_area_bigger = gpd_all_areas_dis.loc[gpd_all_areas_dis.cost_limit <= l_cost_list[i]]
            p_area_smaller = gpd_all_areas_dis.loc[gpd_all_areas_dis.cost_limit <= l_cost_list[i+1]]

            p_area_diff = p_area_bigger.overlay(p_area_smaller[['geometry']], how='difference') 
            p_area_diff = p_area_diff[['cost_limit', 'geometry']] 
            gpd_service_areas_result = pd.concat([gpd_service_areas_result, p_area_diff])

        gpd_service_areas_result = pd.concat([gpd_service_areas_result, p_area_smaller])
        gpd_service_areas_result.reset_index(inplace=True, drop=True)

        return gpd_service_areas_result
    
    else:
        return gpd_all_areas_dis
# create a dissolving / export funtion
""" gdf_all_service_areas_edges.to_file(f"{v_path}/servicearea_edges_alllocs.geojson", driver='GeoJSON')
gdf_all_service_areas_edges = gdf_all_service_areas_edges.loc[gdf_all_service_areas_edges.category != 'loc']
gdf_all_service_areas_edges = remove_semiedges_overlaping_edges(gdf_all_service_areas_edges)
gdf_all_service_areas_edges = remove_duplicated_edges(gdf_all_service_areas_edges)
gdf_all_service_areas_edges.to_file(f"{v_path}/servicearea_edges.geojson", driver='GeoJSON')

# dissolve areas by origen
if export == "dissolved": 
    gpd_all_service_areas_dis = dissolve_service_areas_polygons( gpd_all_service_areas, v_type=dissolve_type)
    gpd_all_service_areas_dis.to_file(f"{v_path}/servicearea_pol.geojson", driver='GeoJSON') 
else:
    gpd_all_service_areas.to_file(f"{v_path}/servicearea_pol.geojson", driver='GeoJSON')  """