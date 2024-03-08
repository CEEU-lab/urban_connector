import geopandas as gpd
from shapely.geometry import Point, LineString

# *******************  GRAPH FROM POINTS AND LINES

def get_edges_geom_from_id(row, dict_mapping_nodes):
    coord_node_st = dict_mapping_nodes['map_nodes'][row.node_id_st].coords[0]
    coord_node_en = dict_mapping_nodes['map_nodes'][row.node_id_en].coords[0]
    return LineString([coord_node_st, coord_node_en])

def map_geom_nodes_rel(graph):
    dict_nodes = dict(zip(list(graph.nodes), [Point(graph.nodes[n]['coords']) for n in list(graph.nodes)]))
    dict_geom = dict(zip([Point(graph.nodes[n]['coords']) for n in list(graph.nodes)], list(graph.nodes)))
    dict_mapping_nodes = {'map_nodes':dict_nodes, 'map_geom':dict_geom}
    return dict_mapping_nodes

# extract points and linestrings from graph, and the mapping relationship between nodes ids and geometry 
def create_geodata_from_graph(graph):
    dict_mapping_nodes = map_geom_nodes_rel(graph)

    gdf_nodes = gpd.GeoDataFrame(dict_mapping_nodes['map_nodes'].items(), columns=['node_id', 'geometry'], geometry='geometry')
    
    dict_edges = [graph.edges[e] for e in list(graph.edges)]
    list_edges_id = list(graph.edges)
    for idx, ele in enumerate(dict_edges):
            ele['edge_id'] = list_edges_id[idx]
    gdf_edges = gpd.GeoDataFrame(dict_edges, geometry='geometry')

    gdf_edges.reversed = gdf_edges.reversed.astype(str)
    gdf_edges.osmid = gdf_edges.osmid.astype(str)
    gdf_edges['node_id_st'] = gdf_edges.apply(lambda row: row.edge_id[0], axis=1)
    gdf_edges['node_id_en'] = gdf_edges.apply(lambda row: row.edge_id[1], axis=1)
    gdf_edges.loc[gdf_edges.geometry.isnull(), 'geometry'] = gdf_edges.loc[gdf_edges.geometry.isnull()].apply(lambda row:  get_edges_geom_from_id(row, dict_mapping_nodes), axis=1)

    gdf_edges.weight = gdf_edges.weight.astype(float)

    gdf_nodes.crs = graph.graph['crs']
    gdf_edges.crs = graph.graph['crs']

    return [gdf_nodes, gdf_edges, dict_mapping_nodes]