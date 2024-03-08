import pandas as pd
import networkx as nx


##**************  CENTRALITIES

def calculate_degree_centrality(graph):
    degree_centrality = nx.degree_centrality(graph)
    return degree_centrality

def calculate_closeness_centrality(graph, v_weight='weight'):
    close_centrality = nx.closeness_centrality(graph, distance=v_weight)
    return close_centrality

def calculate_eigenvector_centrality(graph, v_k=1000, v_weight='weight'):
    eigen_centrality = nx.eigenvector_centrality(graph, max_iter=v_k, weight=v_weight)
    return eigen_centrality

def calculate_betweenness_centrality(graph, object_type, nodes_ids=False, v_k=1000, v_weight='weight'):

    if object_type == 'Point':
        if nodes_ids != False:
            between_centrality = nx.betweenness_centrality_subset(graph, sources=nodes_ids, targets=list(graph.nodes), weight=v_weight)
        else:
            between_centrality = nx.betweenness_centrality(graph, k=v_k, weight=v_weight)
        return between_centrality
    
    elif object_type == 'LineString':
        if nodes_ids != False:
            between_centrality = nx.edge_betweenness_centrality_subset(graph, sources=nodes_ids, targets=list(graph.nodes), weight=v_weight)
        else:
            between_centrality = nx.edge_betweenness_centrality(graph, k=v_k, weight=v_weight)
        return between_centrality
    
    else:
        print(f"object_type parameter posible values: 'nodes' or 'edges'.-")

def calculate_load_centrality(graph, v_weight='weight'):
    load_centrality = nx.load_centrality(graph, weight=v_weight)
    return load_centrality

##**************  ASIGN VALUES TO NODES OR EDGES

def merge_centrality_values_to_nodes(gdf_nodes, centrality_values):
    df_edges_centrality = pd.DataFrame(list(centrality_values.items()), columns=['node_id', 'centrality'])
    edges_centrality = gdf_nodes.merge(df_edges_centrality[['centrality', 'node_id']], on='node_id', how='left')
    return edges_centrality

def merge_centrality_values_to_edges(gdf_edges, centrality_values):
    df_edges_centrality = pd.DataFrame(list(centrality_values.items()), columns=['Key', 'centrality'])

    df_edges_centrality['node_start'] = df_edges_centrality.apply(lambda row: row.Key[0], axis=1)
    df_edges_centrality['node_end'] = df_edges_centrality.apply(lambda row: row.Key[1], axis=1)

    df_edges_centrality['node_st_en'] = df_edges_centrality.apply(lambda row: str(row.node_start) +'-'+ str(row.node_end), axis=1)

    gdf_edges['node_st_en'] = gdf_edges.apply(lambda row: str(row.node_id_st) +'-'+ str(row.node_id_en), axis=1)
    edges_centrality = gdf_edges.merge(df_edges_centrality[['centrality', 'node_st_en']], on='node_st_en', how='left')

    return edges_centrality
    

##**************  GENERAL FUNCTION

def calcualte_edges_centrality(graph, gdf_geom, centrality_type, nodes_ids=False, v_k=1000, v_weight='weight'):

    geometry_type = list(gdf_geom.geom_type)[0]

    print(f"Calculate {centrality_type} centrality")
    if centrality_type == 'degree':
        if geometry_type == 'Point':
            centrality_values = calculate_degree_centrality(graph)
            edges_centrality = merge_centrality_values_to_nodes(gdf_geom, centrality_values)
            return edges_centrality
        else:
            print(f"gdf_geom geometry must be Point.-") 
    
    elif centrality_type == 'closeness':
        if geometry_type == 'Point':
            centrality_values = calculate_closeness_centrality(graph, v_weight=v_weight)
            edges_centrality = merge_centrality_values_to_nodes(gdf_geom, centrality_values)
            return edges_centrality
        else:
            print(f"gdf_geom geometry must be Point.-") 
    
    elif centrality_type == 'eigenvector':
        if geometry_type == 'Point':
            centrality_values = calculate_eigenvector_centrality(graph, v_k=v_k, v_weight=v_weight)
            edges_centrality = merge_centrality_values_to_nodes(gdf_geom, centrality_values)
            return edges_centrality
        else:
            print(f"gdf_geom geometry must be Point.-") 
    
    elif centrality_type == 'betweenness': 
        if geometry_type == 'Point':
            centrality_values = calculate_betweenness_centrality(graph, 'Point', nodes_ids, v_k=v_k, v_weight=v_weight)
            edges_centrality = merge_centrality_values_to_nodes(gdf_geom, centrality_values)
            return edges_centrality
        if geometry_type == 'LineString':
            centrality_values = calculate_betweenness_centrality(graph, 'LineString', nodes_ids, v_k=v_k, v_weight=v_weight)
            edges_centrality = merge_centrality_values_to_edges(gdf_geom, centrality_values)
            return edges_centrality
        else:
            print(f"gdf_geom geometry must be Point or LineString.-") 

    elif centrality_type == 'load':
        if geometry_type == 'Point':
            centrality_values = calculate_load_centrality(graph, v_weight=v_weight)
            edges_centrality = merge_centrality_values_to_edges(gdf_geom, centrality_values)
            return edges_centrality
        else:
            print(f"gdf_geom geometry must be Point.-")
        
    else:
        print(f"centrality_type parameter posible values: 'degree', 'closeness', 'eigenvector', 'betweenness' or 'load'.-") 


