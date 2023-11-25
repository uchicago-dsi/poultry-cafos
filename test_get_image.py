# TODO: Create a testing directory

# TODO: This is maybe a me (Todd) problem, but I had to run:
# python -m pytest test_get_image.py
# to get this to work

import pytest 
import pystac_client
import pystac
import planetary_computer
from get_image import get_tif_image

catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

def test_get_tif_with_wild_bbox():
    # coordinate outside the US
    assert get_tif_image([1,2,3,4], catalog, time_range="2018-01-01/2023-01-01") is None


def test_get_an_Item():
    # check if the output is a pystac.item.Item
    assert isinstance(get_tif_image([-77.61704236937271, 34.85283247747748, -77.5621360306273, 34.89787752252252], \
        catalog, time_range="2018-01-01/2023-01-01"), pystac.item.Item) 