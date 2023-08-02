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
import json
import matplotlib.pyplot as plt
import cv2

import output

class HeatMapOutput(output.Output) :
    """Output Class for heat map

    Args:
        Output (class): Output interface class
    """

    def __init__(self, config, image_info, param_info):
        # Init
        self._counter = 0

        # Get config param
        output_dir = config['output_dir']

        # Make output json directory
        self._json_output_dir = os.path.join(output_dir, 'detect/')
        os.makedirs(self._json_output_dir, exist_ok=True)

        # Output video setting
        video_output_dir = os.path.join(output_dir, 'video/')
        os.makedirs(video_output_dir, exist_ok=True)

        output_name = image_info['image_name']
        frame_rate = config['output_video_fps']
        self._param = {}
        self._param['width'] = config['output_video_width']
        self._param['height'] = config['output_video_height']
        self._param['cmap'] = config['cmap']
        self._param['fcolorbar'] = config['cbar']
        self._param['min'] = config['min']
        self._param['max'] = config['max']
        self._param['foverlay'] = config['overlay']
        self._param['transparency'] = config['transparency']

        if isinstance(output_name, str) and output_name:
            video_file_name = video_output_dir + output_name + '_heatmap.mp4'
        else:
            video_file_name = video_output_dir + 'heatmap.mp4'
        fourcc = cv2.VideoWriter_fourcc('m','p','4','v')
        self._video_writer = cv2.VideoWriter(
            video_file_name, fourcc, frame_rate,
            (self._param['width'], self._param['height'])
        )

        self._param_info = {}
        self._param_info['image_size_h'] = param_info['image_size_h']
        self._param_info['image_size_v'] = param_info['image_size_v']
        self._param_info['grid_num_h'] = param_info['grid_num_h']
        self._param_info['grid_num_v'] = param_info['grid_num_v']
        self._param_info['grid_size_h'] = param_info['grid_size_h']
        self._param_info['grid_size_v'] = param_info['grid_size_v']
        if self._param['max'] == 0:
            self._param['max'] = param_info['last_valid_frame']

    def __del__(self):
        self._video_writer.release()


    def __call__(self, dict_meta, image=None, timestamp=None):
        """output heat map result

        Args:
            dict_meta (dict): meta data
            image (numpy.ndarray, optional): image data. Defaults to None.
            timestamp (str, optional): timestamp string. Defaults to None.
        """

        # add timestamp for json output
        if timestamp is not None:
            dict_meta['timestamp'] = timestamp

        # output json
        if timestamp is not None:
            json_file_name = timestamp
        else:
            json_file_name = f'{self._counter:08d}'
            self._counter += 1

        with open(self._json_output_dir + json_file_name + '.json',
                            'w', encoding='utf-8') as file:
            json.dump(dict_meta, file, indent=4)

        # output movie
        plt.clf()
        plt.cla()

        fig, axs = plt.subplots(
            figsize=[
                self._param_info['image_size_h']/100,
                self._param_info['image_size_v']/100
            ],
            dpi=100
        )

        if self._param['foverlay'] is True and image is not None:
            cv2.imwrite('./input_tmp.jpg', image)
            img = plt.imread('./input_tmp.jpg')
            plt.imshow(img) # input image
            os.remove('./input_tmp.jpg')
        else:
            # Transparency is fixed at 1.0 without image composition
            self._param['transparency'] = 1.0

        # grid To pixel conversion before image compositing
        heat_data = [
            [0 for _ in range(self._param_info['image_size_h'])]
                for _ in range(self._param_info['image_size_v'])]

        for grid_v,_ in enumerate(dict_meta['griddata']):
            for grid_h,_ in enumerate(dict_meta['griddata'][grid_v]):
                for v_g in range(0,self._param_info['grid_size_v']):
                    for h_g in range(0,self._param_info['grid_size_h']):
                        heat_data[grid_v*self._param_info['grid_size_v'] + v_g] \
                            [grid_h*self._param_info['grid_size_h'] + h_g] = \
                            dict_meta['griddata'][grid_v][grid_h]

        img = plt.imshow(
            heat_data,
            vmin=self._param['min'],
            vmax=self._param['max'],
            cmap=self._param['cmap'],
            alpha=self._param['transparency']
        )

        if self._param['fcolorbar'] is True :
            fig.colorbar(img, ax=axs, label='colorbar label')    # colorbar
        plt.axis('off')
        plt.savefig(
            './output_tmp.jpg', bbox_inches='tight', pad_inches=0)    # Axis Untitled
        plt.close()

        # write video
        image = cv2.imread('./output_tmp.jpg')
        image = cv2.resize(image, (self._param['width'], self._param['height']))
        text = f'number of detects : {dict_meta["number_of_detects"]}'
        font_scale = min(self._param['width'], self._param['height']) * 0.001
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 0
        )
        cv2.putText(
            image, text, (5, (2*text_height)),
            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,225,0), 1, cv2.LINE_AA
        )
        self._video_writer.write(image)
        os.remove('./output_tmp.jpg')
