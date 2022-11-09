import streamlit as st
import geopandas as gpd
import pandas as pd


@st.cache(allow_output_mutation=True)
def get_graph_from_dir():
    G = 'read graph from source here'
    return G