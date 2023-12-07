import geopandas as gpd
import ee
import argparse as ap

service_account = 'earth-engine-rafi@rafi-usa.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(service_account, '.private-key.json')
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


def save_to_geojson(filtered_df):

    filtered_df.to_file("final_data.geojson", driver='GeoJSON')
    print("The final dataframe has been saved to final_data.geojson")
    return None


def main():
    df = load_data(args.path)
    filtered_df = filter_by_postprocess_rule(df)
    filtered_df = add_label_and_filter(filtered_df)
    save_to_geojson(filtered_df)

if __name__ == "__main__":
    main()
