import os
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from xarray import DataArray, Dataset

import echoregions as er

data_dir = "./echoregions/test_data/"
output_csv = data_dir + "output_CSV/"
output_json = data_dir + "output_JSON/"


# helper function to read Sv with depth dimension from file folders based on region ids.
# once the new format is incorporated in Sv,
# this step can be simplified and the function may not be needed.
def read_Sv(SONAR_PATH_Sv, SONAR_PATH_raw, region_ids):
    evr_paths = data_dir + "x1.evr"
    r2d = er.read_evr(evr_paths)

    # Select the file(s) that a region is contained in.
    raw_files = os.listdir(SONAR_PATH_raw)
    select_raw_files = r2d.select_sonar_file(raw_files, region_ids)

    # Select the file(s) that a region is contained in.
    Sv_files = os.listdir(SONAR_PATH_Sv)
    select_Sv_files = r2d.select_sonar_file(Sv_files, region_ids)

    # convert a single file output to a list of one element
    if type(select_Sv_files) == str:
        select_Sv_files = [select_Sv_files]
    # convert a single file output to a list of one element
    if type(select_raw_files) == str:
        select_raw_files = [select_raw_files]

    # reading the selected Sv files into one dataset
    Sv = xr.open_mfdataset(
        [os.path.join(SONAR_PATH_Sv, item) for item in select_Sv_files]
    )

    # creating a depth dimension for Sv:

    # reading the processed platform data
    ds_plat = xr.open_mfdataset(
        [os.path.join(SONAR_PATH_raw, item) for item in select_raw_files],
        concat_dim="ping_time",
        combine="nested",
        group="Platform",
    )
    # assuming water level is constant
    water_level = ds_plat.isel(location_time=0, frequency=0, ping_time=0).water_level
    del ds_plat

    Sv_range = Sv.range.isel(frequency=0, ping_time=0)

    # assuming water levels are same for different frequencies and location_time
    depth = water_level + Sv_range
    depth = depth.drop_vars("frequency")
    depth = depth.drop_vars("location_time")
    # creating a new depth dimension
    Sv["depth"] = depth
    Sv = Sv.swap_dims({"range_bin": "depth"})
    return Sv


# helper function to read Sv with depth dimension from file folders based on a list of files
# (both raw and sv need to be supplied at this time
# once the new format is incorporated in Sv,
# this step can be simplified and the function may not be needed.
def read_Sv_from_paths(
    SONAR_PATH_Sv, SONAR_PATH_raw, select_Sv_files, select_raw_files
):
    # reading the selected Sv files into one dataset
    Sv = xr.open_mfdataset(
        [os.path.join(SONAR_PATH_Sv, item) for item in select_Sv_files]
    )

    # creating a depth dimension for Sv:

    # reading the processed platform data
    ds_plat = xr.open_mfdataset(
        [os.path.join(SONAR_PATH_raw, item) for item in select_raw_files],
        concat_dim="ping_time",
        combine="nested",
        group="Platform",
    )
    # assuming water level is constant
    water_level = ds_plat.isel(location_time=0, frequency=0, ping_time=0).water_level
    del ds_plat

    Sv_range = Sv.range.isel(frequency=0, ping_time=0)

    # assuming water levels are same for different frequencies and location_time
    depth = water_level + Sv_range
    depth = depth.drop_vars("frequency")
    depth = depth.drop_vars("location_time")
    # creating a new depth dimension
    Sv["depth"] = depth
    Sv = Sv.swap_dims({"range_bin": "depth"})
    return Sv


# TODO: Make a new region file with only 1 region,
# and check for the exact value for all fields


def test_plot():
    """
    Test region plotting.
    """
    evr_path = data_dir + "x1.evr"
    r2d = er.read_evr(evr_path, min_depth=0, max_depth=100)
    df = r2d.data.loc[r2d.data["region_name"] == "Chicken nugget"]
    r2d.plot([11], color="k")
    assert df["depth"][10][0] == 102.2552007996
    assert df["time"][10][0] == np.datetime64("2017-06-25T20:01:47.093000000")


def test_select_sonar_file():
    """
    Test sonar file selection based on region bounds.
    """
    raw_files = [
        "Summer2017-D20170625-T124834.nc",
        "Summer2017-D20170625-T132103.nc",
        "Summer2017-D20170625-T134400.nc",
        "Summer2017-D20170625-T140924.nc",
        "Summer2017-D20170625-T143450.nc",
        "Summer2017-D20170625-T150430.nc",
        "Summer2017-D20170625-T153818.nc",
        "Summer2017-D20170625-T161209.nc",
        "Summer2017-D20170625-T164600.nc",
        "Summer2017-D20170625-T171948.nc",
        "Summer2017-D20170625-T175136.nc",
        "Summer2017-D20170625-T181701.nc",
        "Summer2017-D20170625-T184227.nc",
        "Summer2017-D20170625-T190753.nc",
        "Summer2017-D20170625-T193400.nc",
        "Summer2017-D20170625-T195927.nc",
        "Summer2017-D20170625-T202452.nc",
        "Summer2017-D20170625-T205018.nc",
    ]

    # Parse region file
    evr_paths = data_dir + "x1.evr"
    r2d = er.read_evr(evr_paths)
    raw = r2d.select_sonar_file(raw_files, 11)
    assert raw == ["Summer2017-D20170625-T195927.nc"]


def test_select_region():
    """
    tests select region functionality
    """
    evr_path = data_dir + "x1.evr"
    r2d = er.read_evr(evr_path)
    region_id = 2
    time_range = [
        pd.to_datetime("2017-06-24T16:31:36.338500000"),
        pd.to_datetime("2017-06-26T16:31:40.211500000"),
    ]
    depth_range = [-10000.0, 10000.0]
    df_1 = r2d.select_region(region_id=region_id)
    df_2 = r2d.select_region(time_range=time_range)
    df_3 = r2d.select_region(depth_range=depth_range)
    for df_region_id in df_1["region_id"]:
        assert df_region_id == region_id
    for time_array in df_2["time"]:
        for time in time_array:
            assert time >= time_range[0]
            assert time <= time_range[1]
    for depth_array in df_3["depth"]:
        for depth in depth_array:
            assert depth >= depth_range[0]
            assert depth <= depth_range[1]


@pytest.mark.filterwarnings("ignore:No gridpoint belongs to any region")
def test_mask_no_overlap():
    """
    test if mask is empty when there is no overlap
    """
    evr_path = data_dir + "x1.evr"
    r2d = er.read_evr(evr_path)
    region_ids = r2d.data.region_id.values

    # we will create a 15 minute window around the bounding box of the region
    bbox_left = r2d.data[r2d.data.region_id.isin(region_ids)].region_bbox_right.iloc[
        0
    ] + timedelta(minutes=15)
    bbox_right = bbox_left + timedelta(minutes=15)

    da_Sv = xr.open_dataset(os.path.join(data_dir, "x1_test.nc")).Sv

    r2d.min_depth = da_Sv.depth.min()
    r2d.max_depth = da_Sv.depth.max()

    # select a chunk of the dataset after the region so there is no overlap
    Sv_no_overlap = da_Sv.sel(ping_time=slice(bbox_left, bbox_right))

    M = r2d.mask(Sv_no_overlap, [11])

    assert isinstance(M, DataArray)
    assert M.isnull().data.all()


def test_mask_correct_labels():
    """testing if the generated id labels are as expected"""

    evr_path = data_dir + "x1.evr"
    r2d = er.read_evr(evr_path)
    region_ids = r2d.data.region_id.values  # Output is that of IntegerArray
    region_ids = list(region_ids)  # Convert to List
    # Convert numpy numeric values to basic Python float values
    region_ids = [region_id.item() for region_id in region_ids]
    da_Sv = xr.open_dataset(os.path.join(data_dir, "x1_test.nc")).Sv
    M = r2d.mask(da_Sv, region_ids, mask_labels=region_ids)
    # it matches only a 11th region becasue x1_test.nc is a chunk around that region only
    M.plot()
    # from matplotlib import pyplot as plt
    # plt.show()
    M = M.values
    assert set(np.unique(M[~np.isnan(M)])) == {11}


def test_select_type_error():
    """
    Tests select error functionality for regions.
    """

    evr_paths = data_dir + "x1.evr"
    r2d = er.read_evr(evr_paths)
    with pytest.raises(TypeError):
        empty_dataset = Dataset()
        _ = r2d.select_region(empty_dataset)
    with pytest.raises(TypeError):
        empty_tuple = ()
        _ = r2d.select_region(empty_tuple)


def test_mask_type_error():
    """
    Tests mask error functionality for regions.
    """

    evr_paths = data_dir + "x1.evr"
    r2d = er.read_evr(evr_paths)
    da_Sv = xr.open_dataset(os.path.join(data_dir, "x1_test.nc")).Sv
    with pytest.raises(TypeError):
        empty_tuple = ()
        _ = r2d.mask(da_Sv, empty_tuple)
    with pytest.raises(ValueError):
        empty_list = []
        _ = r2d.mask(da_Sv, empty_list)


def test_mask_2d_3d_2d_3d():
    """
    Testing if converting 2d-3d-2d-3d masks works.
    """

    evr_path = data_dir + "x1.evr"
    r2d = er.read_evr(evr_path)

    # Extract region_ids
    region_ids = r2d.data.region_id.astype(float).to_list()

    da_Sv = xr.open_dataset(os.path.join(data_dir, "x1_test.nc")).Sv
    M = r2d.mask(da_Sv, region_ids, mask_labels=region_ids)

    # Give mask multiple unique non-nan data points. Necessary for non-trivial one hot encoding
    np_data = M.data
    fake_values = [5.0, 8.0]
    rng = np.random.default_rng(seed=0)
    for index in np.ndindex(np_data.shape):
        if np.isnan(np_data[index]):
            random_float = rng.random()
            if random_float < 0.0044:
                if random_float <= 0.0022:
                    np_data[index] = fake_values[0]
                else:
                    np_data[index] = fake_values[1]
    M.data = np_data

    # Test values from converted 3D array (previous 2D array)
    mask_3d_ds = er.convert_mask_2d_to_3d(M)
    assert mask_3d_ds.mask_3d.shape == (3, 3957, 232)
    assert list(mask_3d_ds.mask_dictionary) == [5.0, 8.0, 11.0]

    # Test values from converted 2D array (previously 3D array)
    mask_2d_da = er.convert_mask_3d_to_2d(mask_3d_ds)
    assert mask_2d_da.equals(M)

    # Test values from 3D array (previously 2D array)
    second_mask_3d_ds = er.convert_mask_2d_to_3d(mask_2d_da)
    assert second_mask_3d_ds.equals(mask_3d_ds)


@pytest.mark.filterwarnings("ignore:No gridpoint belongs to any region")
def test_nan_mask_2d_3d_2d_3d():
    """
    Testing if converting 2d-3d-2d-3d masks works for nan mask.
    """
    evr_path = data_dir + "x1.evr"
    r2d = er.read_evr(evr_path)

    da_Sv = xr.open_dataset(os.path.join(data_dir, "x1_test.nc")).Sv

    M = r2d.mask(da_Sv, [10])

    assert isinstance(M, DataArray)
    assert M.isnull().all()

    # Test values from converted 3D array (previous 2D array)
    mask_3d_ds = er.convert_mask_2d_to_3d(M)
    assert np.unique(mask_3d_ds.mask_3d.data)[0] == 0

    # Test values from converted 2D array (previously 3D array)
    mask_2d_da = er.convert_mask_3d_to_2d(mask_3d_ds)
    assert mask_2d_da.equals(M)
    assert mask_2d_da.isnull().all()

    # Test values from 3D array (previously 2D array)
    second_mask_3d_ds = er.convert_mask_2d_to_3d(mask_2d_da)
    assert second_mask_3d_ds.equals(mask_3d_ds)


def test_one_label_mask_2d_3d_2d_3d():
    """
    Testing if converting 2d-3d-2d-3d masks works for 1 label mask.
    """
    # Create Regions2d Object
    evr_path = data_dir + "x1.evr"
    r2d = er.read_evr(evr_path)

    # Open Dataset and extract DataArray
    da_Sv = xr.open_dataset(os.path.join(data_dir, "x1_test.nc")).Sv

    # Extract region_ids
    region_ids = r2d.data.region_id.astype(float).to_list()

    # Create mask
    M = r2d.mask(da_Sv, region_ids, mask_labels=region_ids)

    # Test values of 2D Mask
    M_values = M.values
    assert set(np.unique(M_values[~np.isnan(M_values)])) == {11}
    assert M.shape == (3957, 232)

    # Test values from converted 3D array (previous 2D array)
    mask_3d_ds = er.convert_mask_2d_to_3d(M)
    assert list(mask_3d_ds.mask_dictionary) == [11.0]
    assert mask_3d_ds.mask_3d.shape == (1, 3957, 232)

    # Test values from converted 2D array (previously 3D array)
    mask_2d_da = er.convert_mask_3d_to_2d(mask_3d_ds)
    assert mask_2d_da.equals(M)

    # Test values from 3D array (previously 2D array)
    second_mask_3d_ds = er.convert_mask_2d_to_3d(mask_2d_da)
    assert second_mask_3d_ds.equals(mask_3d_ds)


def test_overlapping_mask3d_2d():
    """
    Testing if converting 3d to 2d with overlapping mask produces error.
    """

    evr_path = data_dir + "x1.evr"
    r2d = er.read_evr(evr_path)

    # Extract region_ids
    region_ids = r2d.data.region_id.astype(float).to_list()

    da_Sv = xr.open_dataset(os.path.join(data_dir, "x1_test.nc")).Sv
    M = r2d.mask(da_Sv, region_ids, mask_labels=region_ids)

    # Give mask multiple unique non-nan data points. Necessary for non-trivial one hot encoding
    np_data = M.data
    fake_values = [5.0, 8.0]
    rng = np.random.default_rng(seed=0)
    for index in np.ndindex(np_data.shape):
        if np.isnan(np_data[index]):
            random_float = rng.random()
            if random_float < 0.0044:
                if random_float <= 0.0022:
                    np_data[index] = fake_values[0]
                else:
                    np_data[index] = fake_values[1]
    M.data = np_data

    # Test values from converted 3D array (previous 2D array)
    mask_3d_ds = er.convert_mask_2d_to_3d(M)
    assert mask_3d_ds.mask_3d.shape == (3, 3957, 232)
    assert list(mask_3d_ds.mask_dictionary) == [5.0, 8.0, 11.0]

    # Turn first (0th index) array into all 1s to guarantee overlap
    mask_3d_ds.mask_3d[0] = xr.ones_like(mask_3d_ds.mask_3d[0])

    # Trying to convert 3d mask to 2d should raise ValueError
    with pytest.raises(ValueError):
        er.convert_mask_3d_to_2d(mask_3d_ds)
