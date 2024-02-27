import geopandas as gpd
import pandas as pd
import ee
import argparse as ap
from shapely.geometry import box
from geopandas.tools import sjoin

service_account = 'earth-engine-rafi@rafi-usa.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, 'private-key.json')
ee.Initialize(credentials)

parser = ap.ArgumentParser()
parser.add_argument("path", help="path to the file")
args = parser.parse_args()


def load_data(path):
    '''
    Take in the data from the path and return a dataframe

    Input:
        path: path to the geojson file, usually the output after running the postprocess.py

    Output:
        df: a dataframe with all the information from the geojson file'''

    df = gpd.read_file(path)
    print('The original datafrome has',len(df),'rows')
    return df

def filter_by_postprocess_rule(df):
    '''
    Filter the dataframe by the postprocess rule

    Input:
        df: a dataframe with all the information from the geojson file

    Output:
        filtered_df: a dataframe that has been filtered by the postprocess rule'''

    filtered_df = df.loc[df.rectangle_aspect_ratio.between(3.4, 20.49)].reset_index(drop=True)
    filtered_df = filtered_df.loc[filtered_df.distance_to_nearest_road != 0].reset_index(drop=True)
    filtered_df = filtered_df.loc[filtered_df["area"].between(525.69, 8106.53)]
    print("The dataframe has", len(filtered_df), "rows after post-processing")
    return filtered_df

def get_downtown(df):
    '''
    get the shapefile of downtown areas.
    '''

    charlotte = gpd.read_file('data/geojson_to_filter_out/charlotte.geojson')
    raleigh = gpd.read_file('data/geojson_to_filter_out/raleigh.geojson')
    downtown = gpd.GeoDataFrame(pd.concat([charlotte, raleigh]))
    
    downtown_polygon = downtown.to_crs(df.crs)
    return downtown_polygon

def get_coastlines(df, buffer_distance):
    '''
    get areas that are within a specified buffer distance from the coastline.
    '''
    # Create a buffer around coastlines
    coastline = gpd.read_file('tl_2019_us_coastline/tl_2019_us_coastline.shp')
    # convert to crs where the unit in buffer is meter
    coastline_data = coastline.to_crs(epsg=32633)
    coastline_buffer = coastline_data.buffer(buffer_distance)
    coastline_buffer_gdf = gpd.GeoDataFrame(geometry=coastline_buffer)
    # match crs
    coastline_buffer_gdf = coastline_buffer_gdf.to_crs(df.crs)
    return coastline_buffer_gdf

def get_water_cover(df):
    '''
    get water cover areas
    '''
    water_polygon = gpd.read_file('data/geojson_to_filter_out/NC_water_bodies.geojson')
    # water_polygon = gpd.read_file('USA_Detailed_Water_Bodies.geojson')
    water_polygon = water_polygon.to_crs(df.crs)
    return water_polygon

def exclude_on_location(df):
    downtown_polygon = get_downtown(df)
    coastline_polygon = get_coastlines(df, 150)
    water_polygon = get_water_cover(df)
    intersection_downtwon = sjoin(df, downtown_polygon, how="inner", predicate='intersects', lsuffix='_left', rsuffix='_right')
    print("Number of barns in downtown area:", len(intersection_downtwon))
    filtered_df = df[~df.index.isin(intersection_downtwon.index)].copy()

    intersection_coastline = sjoin(filtered_df, coastline_polygon, how="inner", predicate='intersects', lsuffix='_left', rsuffix='_right')
    print("Number of barns in coastline area:", len(intersection_coastline))
    filtered_df = filtered_df[~filtered_df.index.isin(intersection_coastline.index)].copy()

    intersection_water = sjoin(filtered_df, water_polygon, how="inner", predicate='intersects', lsuffix='_left', rsuffix='_right')
    print("Number of barns in water area:", len(intersection_water))
    filtered_df = filtered_df[~filtered_df.index.isin(intersection_water.index)].copy()

    print("The dataframe has", len(filtered_df), "rows after revoming downtown, water and coastline.")
    return filtered_df

def get_label_from_ee(df):
    '''
    Find the terrain label for a polygon in the dataframe

    Input:
        df: a dataframe with all the information from the geojson file

    Output:
        majority_class_info['label']: the terrain label for the polygon
    '''

    # The polygons are too small to get land cover data, so pick a point to use (might as well be the centroid)
    centroid_df = df.centroid

    # Create a feature collection from the centroid
    fc = ee.FeatureCollection(ee.Feature(ee.Geometry.Point(centroid_df.x, centroid_df.y)))

    # Use the Dynamic World dataset
    collection = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').filterBounds(fc)

    # Select the 'label' band with information on the majority classification
    landcover = ee.Image(collection.first()).select('label')

    majority_class_info = landcover.reduceRegion(
        reducer=ee.Reducer.first(),
        geometry=fc,
        scale=10  # image resolution is 10m
    ).getInfo()

    return majority_class_info['label']

def exclude_on_land_cover(filtered_df):
    '''
    Add the terrain label as new column to the dataframe and filter out
    the ones that are water label(0)

    Input:
        filtered_df: a dataframe that has been filtered by the postprocess rule

    Output:
        filtered_df: a dataframe that has been filtered by the postprocess
        rule and terrain label'''
    filtered_df['terrain_label'] = filtered_df['geometry'].apply(get_label_from_ee)
    filtered_df = filtered_df[~filtered_df['terrain_label'].isin([0])]

    # Print the filtered dataframe
    print("The dataframe has", len(filtered_df), "rows after label filtering")
    return filtered_df

def save_to_geojson(filtered_df):
    filtered_df.to_file("final_data.geojson", driver='GeoJSON')
    print("The final dataframe has been saved to final_data.geojson")
    return None

def main():
    df = load_data(args.path)
    filtered_df = filter_by_postprocess_rule(df)
    filtered_df_1 = exclude_on_location(filtered_df)
    # uncomment the code to run the google earth api
    # filtered_df = exclude_on_land_cover(filtered_df)
    save_to_geojson(filtered_df_1)

if __name__ == "__main__":
    main()
