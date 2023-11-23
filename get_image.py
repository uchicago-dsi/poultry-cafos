import pystac_client
import planetary_computer
import geopandas
from shapely.geometry import mapping, box, shape
import requests
import argparse

def bbox_geo_item(bbox):
    '''
    Convert a bbox into a Polygon
    
    Input: 
    bbox(list): a bounding box

    Return:
    bbox_geo(polygon): a geojson format item'''
    minx, miny, maxx, maxy = bbox
    bbox_polygon = box(minx, miny, maxx, maxy)

    # Convert the Polygon to a GeoJSON-like format
    bbox_geo = mapping(bbox_polygon)

    return bbox_geo


def area_of_overlap(item, area_shape):
    '''
    Calculate the area of overlap between the item and the bounding box
    
    Input:
    item(item): a geo item
    area_shape(polygon): a geojson format item
    
    Return:
    overlap_area(float): the area of overlap between the item and the bounding box
    '''
    overlap_area = shape(item.geometry).intersection(shape(area_shape)).area
    return overlap_area


def get_tif_image(bbox, catalog, time_range="2018-01-01/2023-01-01"):
    '''
    Find the latest image in the database that overlaps the 
    most with bounding box area.
    
    Input:
    bbox_geo(polygon): a geojson format item
    time_range(str): time range of images
    
    Return:
    image_latest(item): the latest image that overlaps the
     most with the bounding box area
    '''
    # search for any overlapping items in the database
    search = catalog.search(
    collections=["naip"], bbox= bbox, datetime=time_range
    )

    items_lst= search.item_collection()

    # if no items found, stop the program
    if len(items_lst) == 0:
        print("No items found, please try another coordinate")
        return None

    print(f"{len(items_lst)} Items found in the time range")

    # calculate the area of the bounding box
    bbox_geo = bbox_geo_item(bbox)
    area_shape = shape(bbox_geo)
    
    # sort the items by the overlap area and year, only keep the first one
    image_latest = sorted(items_lst, key=lambda item: (area_of_overlap(item,area_shape), item.properties['naip:year']), reverse=True)[0]
    print(f"Latest best-match image found: {image_latest.id}")
    return image_latest


def save_image_to_cloud(image):
    '''
    Save the image to cloud storage
    
    Input:
    image(item): the latest image that overlaps the
     most with the bounding box area
    
    Return:
    save_fpath(str): the path of the saved image
    '''
    tif_url = image.assets["image"].href
    image_fn = tif_url.split('?')[0].split('/')[-1]
    
    save_fpath = f"image_data/{image_fn}"

    # Perform the request to download the TIFF file
    response = requests.get(tif_url, stream=True)

    # Check if the request was successful
    if response.status_code == 200:
        with open(save_fpath, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"File downloaded and saved at {save_fpath}")
    else:
        print(f"Failed to download the file. Status code: {response.status_code}")

    return save_fpath


def save_loc_to_txt(save_fpath, txt_path='data/test-input.txt'):
    '''
    Write the location of the saved image to a txt file for command
    line input
    
    Input:
    save_fpath(str): the path of the saved image
    txt_path(str): the path of the txt file used in command line
    '''
    with open(txt_path, 'w') as f:
        # write text 'image_fn'first and save the location to new line
        f.write('image_fn')
        f.write('\n')
        f.write(f'"{save_fpath}"')
        print(f'saved location writen in {txt_path}')

    return None


def main(bbox):

    # set identifier of database
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

    # set a bounding box of desired area
    #bbox = [-77.61704236937271, 34.85283247747748, -77.5621360306273, 34.89787752252252]
    image = get_tif_image(bbox,catalog)
    save_location = save_image_to_cloud(image)
    save_loc_to_txt(save_location)

    return None


if __name__ == '__main__':
    # Set a bbox
    parser = argparse.ArgumentParser(description="Input a bounding box")
    
    # bbox need four values
    parser.add_argument('--bbox', nargs=4, type=float, required=True,
                        help='Provide bounding box as four space separated values: minx miny maxx maxy')
    
    args = parser.parse_args()

    main(args.bbox)
