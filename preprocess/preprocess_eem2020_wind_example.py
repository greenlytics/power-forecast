#!/usr/bin/python

import os
import sys
import json
import datetime
import numpy as np
import xarray as xr
import pandas as pd
import glob


def load_data(path, splits):
    files = glob.glob(f"{path}/**/*.nc", recursive=True)    
    # reduce the preprocessing to the reference times inside the splits
    ref_times = [pd.to_datetime(f[-15:-3]).to_numpy() for f in files]
    ref_time_indices_from_splits = np.unique(
                                    np.concatenate([
                                        np.where((pd.to_datetime(start).to_numpy()<=ref_times) & (ref_times<pd.to_datetime(end).to_numpy()))[0]
                                             for split_name, split_spec in splits.items()
                                                  for start, end in split_spec]))
    files = np.array(files)[ref_time_indices_from_splits].tolist()
    files = sorted(files)

    ds = xr.open_mfdataset(files, engine='h5netcdf', parallel=True)
    ds_subset = ds.isel(x=slice(0, 71, 20), y=slice(0, 169, 50), ensemble_member=[0, 1, 2]).compute()

    df_production = pd.read_csv(f"{path}/windpower_task0_updated.csv", index_col=0, parse_dates=[0])
    df_production.index = df_production.index.tz_localize(None)

    return ds_subset, df_production


def preprocess_wind(ds_weather, df_production, target, features):

    ds_weather['WindSpeed'] = (ds_weather['Wind_U']**2+ds_weather['Wind_V']**2)**0.5
    ds_weather['WindDirection'] = 180 + xr.ufuncs.degrees(xr.ufuncs.arctan2(ds_weather['Wind_V'], ds_weather['Wind_U']))

    variables = np.unique([f.split('_')[0] for f in features])

    df = pd.DataFrame(index=pd.to_datetime(ds_weather.time.data))
    for var in variables:
        data = ds_weather[var].data.reshape(len(df.index), -1)
        for feature_ix in np.arange(data.shape[1]):
            df.loc[:, f"{var}_{feature_ix}"] = data[:, feature_ix]
    df.index = pd.MultiIndex.from_arrays([df.index.floor("1D"), df.index], names=["ref_datetime", "valid_datetime"])

    # repeat the weather features for each region in df_production
    df = pd.DataFrame(np.tile(df.values, (len(df_production.columns))),
                         index=df.index,
                         columns=pd.MultiIndex.from_product([df_production.columns, df.columns]))
    # add the production target

    for area in df_production.columns:
        df.loc[:, (area, target)] = df_production[area].reindex(index=df.index.get_level_values("valid_datetime")).values

    df.sort_index(axis=1, inplace=True)

    return df.loc[:, pd.IndexSlice[:, [target]+features]]


def save_data(path, filename, df):
    
    if not os.path.exists(path):
        os.makedirs(path)
    df.to_csv(path+filename)


if __name__ == '__main__':
    params_path = sys.argv[1]
    with open(params_path, 'r', encoding='utf-8') as file:
        params_json = json.loads(file.read())

    ds_weather, df_production = load_data(params_json['path_raw_data'], params_json['splits'])
    df = preprocess_wind(ds_weather, df_production, params_json['target'], params_json['features'])
    save_data(params_json['path_preprocessed_data'], params_json['filename_preprocessed_data'], df)
    print('Wind track preprocessed data saved to: '+params_json['path_preprocessed_data']+params_json['filename_preprocessed_data'])

