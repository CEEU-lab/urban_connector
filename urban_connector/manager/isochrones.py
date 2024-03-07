import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import split, snap, nearest_points
import networkx as nx

def split_line_by_point(line_geometry, inter_perc, from_end_or_start):

    if from_end_or_start == 'end':
        inter_perc_calc = 1 - inter_perc
    else:
        inter_perc_calc = inter_perc
    
    v_point_middle_x = line_geometry.interpolate(inter_perc_calc, normalized=True).x
    v_point_middle_y = line_geometry.interpolate(inter_perc_calc, normalized=True).y
    minimum_distance = nearest_points(Point(v_point_middle_x, v_point_middle_y), line_geometry)[1]

    split_line = split(snap(line_geometry, minimum_distance,  0.00001), minimum_distance )
    segments = [feature for feature in split_line.geoms]

    try:
        length_1 = segments[0].length
        length_2 = segments[1].length

        if inter_perc > 0.5:
            if length_1 > length_2:
                new_geom = segments[0]
            else:
                new_geom = segments[1]
        else:
            if length_1 > length_2:
                new_geom = segments[1]
            else:
                new_geom = segments[0]
    except:
        new_geom = line_geometry
        print(line_geometry, inter_perc)

    return new_geom

def calculate_travel_time_to_all_nodes(graph, f_weight, loc_node_list):
    result = nx.multi_source_dijkstra_path_length(graph, 
                                        sources = loc_node_list, 
                                        cutoff=None, 
                                        weight=f_weight)
    df = pd.DataFrame(result.items(), columns=['node_id', 'weight_to'])
    return df

def asign_weight_values_to_nodes_and_edges(gdf_nodes, gdf_edges, df_weight):
    df_nodes= gdf_nodes.merge(df_weight[['node_id', 'weight_to']], on='node_id', how='left')
    df_nodes= df_nodes[['node_id', 'geometry', 'weight_to']]

    df_edges = gdf_edges.merge(df_weight[['node_id', 'weight_to']], left_on='node_id_st', right_on='node_id', how='left')
    df_edges = df_edges.merge(df_weight[['node_id', 'weight_to']], left_on='node_id_en', right_on='node_id', how='left')
    df_edges.rename(columns={'weight_to_x':'w_start', 'weight_to_y':'w_end'}, inplace=True)
    df_edges['w_mean'] = (df_edges['w_start'] + df_edges['w_end'])/2
    df_edges.drop(columns=['node_id_x', 'node_id_y'], inplace=True)

    return df_nodes, df_edges

def create_service_area_by_weight_limit(gdf_edges, weight_limit):

    gdf_edges['cat_limit'] = 'out'
    gdf_edges.loc[(gdf_edges.w_start < weight_limit) & (gdf_edges.w_end < weight_limit), 'cat_limit'] = 'ok'
    df_edges_ok = gdf_edges.loc[gdf_edges.cat_limit == 'ok'].reset_index(drop=True)

    df_edges__from_start = gdf_edges[(gdf_edges.w_start < weight_limit) & (gdf_edges.w_end > weight_limit)].reset_index(drop=True)
    df_edges__from_start['cat_limit'] = 'start'
    df_edges__from_start['weight_delta'] = (weight_limit - df_edges__from_start['w_start']) / (df_edges__from_start['w_end'] - df_edges__from_start['w_start'])

    df_edges_from_end = gdf_edges[(gdf_edges.w_start > weight_limit) & (gdf_edges.w_end < weight_limit)].reset_index(drop=True)
    df_edges_from_end['cat_limit'] = 'end'
    df_edges_from_end['weight_delta'] = (weight_limit - df_edges_from_end['w_end']) / (df_edges_from_end['w_start'] - df_edges_from_end['w_end'])

    df_edges__from_start = df_edges__from_start.to_crs('3857')
    df_edges_from_end = df_edges_from_end.to_crs('3857')
    df_edges__from_start['geometry'] = df_edges__from_start.apply(lambda row: split_line_by_point(row.geometry, row.weight_delta, 'start'), axis=1)
    df_edges_from_end['geometry'] = df_edges_from_end.apply(lambda row: split_line_by_point(row.geometry, row.weight_delta, 'end'), axis=1)
    df_edges__from_start = df_edges__from_start.to_crs(gdf_edges.crs)
    df_edges_from_end = df_edges_from_end.to_crs(gdf_edges.crs)

    df_edges_weight_limit = pd.concat([df_edges_ok, df_edges__from_start, df_edges_from_end])

    df_edges_weight_limit.drop(columns=['cat_limit', 'weight_delta'], inplace=True)
    df_edges_weight_limit['w_limit'] = weight_limit
    return df_edges_weight_limit

def calculate_service_edges(graph, gdf_nodes, gdf_edges, f_weight, v_weight_limit, list_source_nodes):
    df_weight_times = calculate_travel_time_to_all_nodes(graph, f_weight, list_source_nodes)
    gdf_nodes, gdf_edges = asign_weight_values_to_nodes_and_edges(gdf_nodes, gdf_edges, df_weight_times)
    df_edges_weight_limit = create_service_area_by_weight_limit(gdf_edges, v_weight_limit)
    return df_edges_weight_limit


## SERVICES AREAS

# create service area for a single weight limit
def create_service_area(gdf_edges, v_crs_proj, v_buffer_meters, v_dissolve_distance):
    weight_limit_value = list(gdf_edges.w_limit.unique())[0]
    v_dissolve_distance_retract = (-0.99) * v_dissolve_distance
    v_buffer_meters = v_buffer_meters - v_dissolve_distance *0.01

    gdf_edges_buffer = gdf_edges.to_crs(v_crs_proj)
    gdf_edges_buffer.geometry = gdf_edges_buffer.buffer(v_dissolve_distance) # , cap_style=2
    gdf_edges_buffer = gdf_edges_buffer.dissolve(by='w_limit').reset_index(drop=True)

    gdf_edges_buffer.geometry = gdf_edges_buffer.buffer(v_dissolve_distance_retract, cap_style=2)
    gdf_edges_buffer.geometry = gdf_edges_buffer.buffer(v_buffer_meters)

    gdf_edges_buffer['w_limit'] = weight_limit_value
    gdf_edges_buffer = gdf_edges_buffer.to_crs(gdf_edges.crs)

    return gdf_edges_buffer

# merge service areas of different weight limits, into polygons or rings by limit weight
def merge_service_areas_polygons( list_gpd_service_areas, v_type='rings'):

    gpd_all_areas = pd.concat(list_gpd_service_areas) 
    gpd_all_areas = gpd_all_areas.sort_values('w_limit', ascending=True).reset_index(drop=True)
    l_weight_list = list(gpd_all_areas['w_limit'].sort_values(ascending=False))

    if v_type == 'rings':
        gpd_service_areas_result = gpd.GeoDataFrame([], columns=['w_limit', 'geometry'], geometry='geometry')

        for i in range(len(l_weight_list)-1):
            p_area_bigger = gpd_all_areas.loc[gpd_all_areas.w_limit <= l_weight_list[i]]
            p_area_smaller = gpd_all_areas.loc[gpd_all_areas.w_limit <= l_weight_list[i+1]]

            p_area_diff = p_area_bigger.overlay(p_area_smaller[['geometry']], how='difference') 
            p_area_diff = p_area_diff[['w_limit', 'geometry']] 
            gpd_service_areas_result = pd.concat([gpd_service_areas_result, p_area_diff])

        gpd_service_areas_result = pd.concat([gpd_service_areas_result, p_area_smaller])
        gpd_service_areas_result.reset_index(inplace=True, drop=True)

        return gpd_service_areas_result
    
    else:
        return gpd_all_areas
    
## SERVICES AREAS FOR MULTIPLE weight LIMITS
def create_service_area_for_multiple_weights(graph, gdf_nodes, gdf_edges, f_weight , list_weight, list_source_nodes, v_buffer_meters, v_dissolve_distance, area_type='rings', v_crs_proj="3857"): 

    list_weights_buffers = []
    for v_weight_limit in list_weight:
        df_edges_weight_limit = calculate_service_edges(graph, gdf_nodes, gdf_edges, f_weight, v_weight_limit, list_source_nodes)
        df_edges_weight_limit_buffer = create_service_area(df_edges_weight_limit, v_crs_proj, v_buffer_meters, v_dissolve_distance)
        list_weights_buffers.append(df_edges_weight_limit_buffer)

    gdf_service_areas = merge_service_areas_polygons( list_weights_buffers, area_type)

    return gdf_service_areas