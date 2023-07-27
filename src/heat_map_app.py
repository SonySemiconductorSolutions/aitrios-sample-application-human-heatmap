"""
Copyright 2023 Sony Semiconductor Solutions Corp. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
import yaml
import argparse
from tqdm import tqdm

import console_data_loader
import local_data_loader
import heat_map
import heat_map_output


def main():
    """main process

    """

    # Get argument
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_path', type=str, default='config/heat_map_app.yaml')
    args = parser.parse_args()

    # Init
    image_list = []
    meta_list = []
    timestamp_list = []
    data_loader = None
    heat_map_creator = None
    output_writer = None

    # Load config from yaml file
    if os.path.exists(args.config_path):
        with open(args.config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
    else:
        raise ValueError(f'cannot open {args.config_path}')

    # Check config parameter
    if not 'data_source_settings' in config:
        raise ValueError('data source settings is not found')
    if not 'heat_map_settings' in config:
        raise ValueError('heat_map settings is not found')
    if not 'output_settings' in config:
        raise ValueError('output settings is not found')

    # Select get data method and create instance
    if config['data_source_settings']['mode'] == 'console':
        data_loader = console_data_loader.ConsoleDataLoader(
            config['data_source_settings']['console_data_settings'])
    elif config['data_source_settings']['mode'] == 'local':
        data_loader = local_data_loader.LocalDataLoader(
            config['data_source_settings']['local_data_settings'])
    else:
        raise ValueError(
            f"{config['data_source_settings']['mode']} is not supported")
    image_info = data_loader.get_image_info()

    # Load detect config parameter from yaml
    with open(
            config['heat_map_settings']['param_file'], 'r', encoding='utf-8'
        ) as file:
        heat_map_params = yaml.safe_load(file)

    # Create instance of detect class
    heat_map_creator = heat_map.HeatMap(heat_map_params)
    param_info = heat_map_creator.get_param_info()

    # Instance creation of output class
    output_writer = heat_map_output.HeatMapOutput(
        config['output_settings'], image_info, param_info)

    # Load data
    image_list, meta_list, timestamp_list = data_loader()

    # Detect loop
    for i, meta in enumerate(tqdm(meta_list, desc='processing')):

        # check image data
        if len(image_list) > i:
            image = image_list[i]
        else:
            image = None

        # check timestamp
        if len(timestamp_list) > i:
            timestamp = timestamp_list[i]
        else:
            timestamp = None

        # detect Process
        detect = heat_map_creator(meta)

        # output Process
        output_writer(detect, image, timestamp)


if __name__ == '__main__':
    main()
