import pandas as pd
import geopandas as gpd
import osmnx as ox

def build_source_gdf(gdf_sources, field_category=None, field_name=None):
    if 'src_id' in gdf_sources.columns:
        gdf_sources.drop(columns=['src_id'], inplace=True)
    gdf_sources.reset_index(inplace=True, drop=True)
    gdf_sources_2 = gdf_sources.rename_axis('src_id').reset_index()
    gdf_sources_2['src_id'] = gdf_sources_2['src_id']+1
    gdf_sources_2['src_id'] = "src_"+gdf_sources_2['src_id'].astype(str)

    if 'category' not in gdf_sources_2.columns:
        if field_category is not None:
            gdf_sources_2.rename(columns={field_category:'category'}, inplace=True)
        else:
            gdf_sources_2['category'] = None

    if 'name' not in gdf_sources_2.columns:
        if field_name is not None:
            gdf_sources_2.rename(columns={field_name:'name'}, inplace=True)
        else:
            gdf_sources_2['name'] = None

    gdf_sources_2 = gdf_sources_2[['src_id', 'category', 'name', 'geometry']]
    
    return gdf_sources_2

def get_amenities(poly_boundary, amenities):
    gdf_amenities = ox.geometries_from_polygon(poly_boundary, tags={"amenity": amenities}).loc[:, ["name", "amenity", "geometry"]].reset_index(drop=True)
    gdf_amenities.geometry = gdf_amenities.geometry.centroid
    gdf_amenities = build_source_gdf(gdf_amenities, field_category='amenity', field_name='name')
    return gdf_amenities

def add_amenities(pdf_new_amenities, gdf_amenities, list_near_nodes, graph, str_method_near_nodes=['closest']):
    if str_method_near_nodes[0] == 'closest':
        list_node_sources = closest_nodes_to_sources(graph, pdf_new_amenities)
    elif str_method_near_nodes[0] == 'buffer':
        search_node_near_to_sources (pdf_new_amenities, str_method_near_nodes[1], str_method_near_nodes[2])
    else:
        print(f"Parameter str_method_near_nodes values: 'closest', or 'buffer'.-")
        return
    list_node_sources = list_near_nodes + list_node_sources
    gdf_amenities = pd.concat([gdf_amenities, pdf_new_amenities])
    gdf_amenities = build_source_gdf(gdf_amenities, field_category=None, field_name=None)
    return gdf_amenities, list_node_sources

# return list of closest nodes to sources
def get_closest_node(graph, source):
    pt_lon = source.geometry.coords[0][0]
    pt_lat = source.geometry.coords[0][1]
    center_node = ox.distance.nearest_nodes(graph, pt_lon, pt_lat)
    return center_node

def closest_nodes_to_sources(graph, gdf_sources):
    return [get_closest_node(graph, gdf_sources.iloc[source]) for source in range(len(gdf_sources))]

# return id of graph's nodes near sources, by buffer distance
def search_node_near_to_sources (gdf_sources, gdf_nodes, search_radio):
    nodes_in = gdf_nodes.sjoin(gpd.GeoDataFrame(geometry=gdf_sources.buffer(search_radio)))
    nodes_in = nodes_in.drop_duplicates(subset='node_id').reset_index(drop=True)
    node_list = list(nodes_in.node_id)
    return node_list