import geopandas as gpd
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


def find_my_terrain(df):
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


def add_label_and_filter(filtered_df):
    '''
    Add the terrain label as new column to the dataframe and filter out
    the ones that are water label(0)

    Input:
        filtered_df: a dataframe that has been filtered by the postprocess rule

    Output:
        filtered_df: a dataframe that has been filtered by the postprocess
        rule and terrain label'''
    filtered_df['terrain_label'] = filtered_df['geometry'].apply(find_my_terrain)
    filtered_df = filtered_df[~filtered_df['terrain_label'].isin([0])]

    # Print the filtered dataframe
    print("The dataframe has", len(filtered_df), "rows after label filtering")
    return filtered_df

def filter_out_downtown_charlotte(df):
    '''
    Filter out items located in the downtown Charlotte area using the defined bounding box.
    '''
    downtown_bbox = (-80.857, 35.215, -80.836, 35.230)
    downtown_polygon = box(*downtown_bbox)
 
    df['is_in_downtown'] = df['geometry'].apply(lambda x: x.centroid.within(downtown_polygon))
    # Filter out those within the downtown area
    filtered_df = df[~df['is_in_downtown']].copy()
    print("The dataframe has", len(filtered_df), "rows after removing dt area")
    return filtered_df

def filter_out_coastlines(df, coastline_data, buffer_distance):
    '''
    Filter out polygons that are within a specified buffer distance from the coastline.
    '''
    # Create a buffer around coastlines
    coastline_data = coastline_data.to_crs(epsg=32633)
    coastline_buffer = coastline_data.buffer(buffer_distance)
    coastline_buffer_gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(coastline_buffer))
    coastline_buffer_gdf = coastline_buffer_gdf.to_crs(df.crs)
    
    # Spatial Join
    intersections = sjoin(df, coastline_buffer_gdf, how="inner", op='intersects', lsuffix='_left', rsuffix='_right')

    # Filter out polygons that intersect with the coastline buffer
    filtered_df = df[~df.index.isin(intersections.index)].copy()

    print("The dataframe has", len(filtered_df), "rows after removing coastline area")
    return filtered_df

def filter_out_airports(df, airport_data, dist_km):
    '''
    ** Need to have airports.geojson in root directory first **
    Filter out the poultry barns which are at within a range of distance (buffer) of an international airport

    Input:
        df: a dataframe that has been filtered by the postprocess rule and filter down to the desired location
        airport_data: a dataframe of international airports (could either be filtered to the desired location or unfiltered)
        dist_km: a buffer distance in kilometers (integer) that reasonably rules out the existence of poultry barns

    Output:
        df_clean: poultry barns data excluding the airports'''
    
    # Transform buffer distance in kilometers to projection distance in EPSG 4326
    dist_meters = dist_km * 1000
    dist_project = dist_meters / 111120

    # Creat the buffer
    buffer_series = airport_data[['geometry']].buffer(dist_project)
    buffer_gpd = gpd.GeoDataFrame(geometry=buffer_series)
    intersection = df.overlay(buffer_gpd, how='intersection') # find barns within a range of distance of an airport
    df_clean = df.overlay(intersection, how='difference') # exclude the intersection

    return df_clean

def save_to_geojson(filtered_df):

    filtered_df.to_file("final_data.geojson", driver='GeoJSON')
    print("The final dataframe has been saved to final_data.geojson")
    return None


def main():
    df = load_data(args.path)
    filtered_df = filter_by_postprocess_rule(df)
    filtered_df_1 = add_label_and_filter(filtered_df)
    filtered_df_2 = filter_out_downtown_charlotte(filtered_df_1)
    coastline = gpd.read_file('tl_2019_us_coastline/tl_2019_us_coastline.shp')
    filtered_df_3 = filter_out_coastlines(filtered_df_2, coastline, buffer_distance=200)
    save_to_geojson(filtered_df_3)

if __name__ == "__main__":
    main()
