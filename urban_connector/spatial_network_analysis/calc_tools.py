import geopandas as gpd

def extract_nearedge_parameters(gdf_edges, f_cost):
    l_params = gdf_edges[['node_start', 'node_end', f_cost]].values.flatten().tolist()
    v_length = list(gdf_edges.length)[0]

    return [l_params[0], l_params[1], l_params[2], v_length]

""" def nearest_edge_to_point_parameters(gdf_point, gdf_edges, f_cost, v_max_dist):

    gdf_edges['pt_dist'] = [list(gdf_point.distance(line))[0] for line in gdf_edges.geometry]

    v_min_dist = list(gdf_edges.loc[gdf_edges['pt_dist'] == gdf_edges['pt_dist'].min(), 'pt_dist'])[0]
    if v_min_dist <= v_max_dist:
        v_target_pt_1, v_target_pt_2, v_target_w, v_length_line = extract_line_parameters(gdf_edges, f_cost, 'pt_dist')
        return [v_target_pt_1, v_target_pt_2, v_target_w, v_length_line]
    else:
        return [0, 0, 0, 0] """
# find nearest line to point - better performance
def nearest_edge_to_point(gdf_point, gdf_edges):
    gdf_nearest_line = gpd.sjoin_nearest(gdf_point[['geometry']], gdf_edges).merge(gdf_edges[['geometry']], left_on="index_right", right_index=True)
    gdf_nearest_line["distance"] = gdf_nearest_line.apply(lambda row: row["geometry_x"].distance(row["geometry_y"]), axis=1)
    gdf_nearest_line = gpd.GeoDataFrame(gdf_nearest_line, geometry='geometry_y')
    return gdf_nearest_line


# find nearest line to point and return its parameters 
def nearest_edge_to_point_parameters(gdf_point, gdf_edges, f_cost, v_max_dist):
    
    gdf_nearest_line = nearest_edge_to_point(gdf_point, gdf_edges)
    v_min_dist = gdf_nearest_line['distance'].min()

    if (v_min_dist < v_max_dist):
        v_target_pt_1, v_target_pt_2, v_target_w, v_length_line = extract_nearedge_parameters(gdf_nearest_line, f_cost)
        return v_target_pt_1, v_target_pt_2, v_target_w, v_length_line
    else:
        return 0, 0, 0, 0

def calculate_weight_to_node_of_nearest_edge(gdf_point, gdf_node, v_node_id, v_length_line, v_weight):
    pnt1 = list(gdf_point.geometry)[0]
    pnt2 = list(gdf_node.loc[gdf_node.node_id == v_node_id].geometry)[0]
    points_df = gpd.GeoDataFrame({'geometry': [pnt1, pnt2]}, crs=gdf_point.crs)
    points_df2 = points_df.shift() #We shift the dataframe by 1 to align pnt1 with pnt2
    # points_df = points_df.to_crs("3857")
    # points_df2 = points_df2.to_crs("3857")
    pt_dist = points_df.distance(points_df2)
    v_weight_result = v_weight * pt_dist[1] / v_length_line

    return v_weight_result