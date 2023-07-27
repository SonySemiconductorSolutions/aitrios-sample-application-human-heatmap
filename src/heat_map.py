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

import queue
import numpy as np

import object_detection_processor

class HeatMap(object_detection_processor.ObjectDetectionProcessor):
    """create heat map data class

    Args:
        ObjectDetectionProcessor (class): Detect interface class
    """

    def __init__(self, config):
        # Init
        self._number_of_add_grid    = 0    # number of peripheral grids to be added
        self._param = {}
        self._param['last_valid_frame'] = 1 # most recent valid frame count
        self._param['image_size_h'] = 0    # image size(horizontal)
        self._param['image_size_v'] = 0    # image size(vertical)
        self._param['grid_num_h'] = 1    # number of grid(horizontal)
        self._param['grid_num_v'] = 1    # number of grid(vertical)
        self._bbox2pix_ratio = 1.0    # vertical ratio of bbox to pixel(0.0~1.0)

        # load parameter from json
        self._number_of_add_grid    = config['number_of_add_grid']
        self._param['last_valid_frame'] = config['last_valid_frame']
        self._param['image_size_h'] = config['image_size_h']
        self._param['image_size_v'] = config['image_size_v']
        self._param['grid_num_h'] = config['grid_num_h']
        self._param['grid_num_v'] = config['grid_num_v']
        self._bbox2pix = config['bbox2pix']

        self._queue = queue.Queue(maxsize=self._param['last_valid_frame'])
        self._griddata = [
                [0 for _ in range(self._param['grid_num_h'])]
                    for _ in range(self._param['grid_num_v'])]

        if ( self._param['image_size_h'] % self._param['grid_num_h'] ) != 0:
            raise RuntimeError('error, image_size_h is not divisible by grid_num_h')
        if ( self._param['image_size_v'] % self._param['grid_num_v'] ) != 0:
            raise RuntimeError('error, image_size_v is not divisible by grid_num_v')
        self._param['grid_size_h'] = \
            self._param['image_size_h'] // self._param['grid_num_h']
        self._param['grid_size_v'] = \
            self._param['image_size_v'] // self._param['grid_num_v']


    def __call__(self, serialize_meta):
        """Create heat map data process

        Args:
            serialize_meta (bytes): serialized meta data

        Returns:
            dict: detect result
        """

        # deserialize meta data
        meta_array = super().deserialize_meta_data(serialize_meta)
        bbox_array = [p[0] for p in meta_array]

        if self._bbox2pix is True:
            bbox_array = self._bbox_to_point(bbox_array)

        # If the queue is full, subtract the oldest data first
        if self._queue.full():
            if self._bbox2pix is False:
                self._dec_bbox(self._get_queue())
            else:
                for pix_h, pix_v in self._get_queue():
                    grid_h, grid_v = self._pix_to_grid(pix_h, pix_v)
                    self._dec_around_grid(grid_h, grid_v)

        self._set_queue(bbox_array)
        if self._bbox2pix is False:
            self._add_bbox(bbox_array)
        else:
            for pix_h,pix_v in bbox_array:
                grid_h, grid_v = self._pix_to_grid(pix_h, pix_v)
                self._add_around_grid(grid_h, grid_v)

        # Output to dict
        result_dict = self._output_to_dict(
            bbox_array, self._griddata)

        return result_dict


    def _output_to_dict(self, detects, griddata):
        if self._bbox2pix is False:
            bbox_dicts = []
            for bbox in detects:
                bbox_dict = {
                    'left': bbox[0],
                    'top': bbox[1],
                    'right': bbox[2],
                    'bottom': bbox[3]
                    }
                bbox_dicts.append(bbox_dict)

            result_dict = {
                'number_of_detects': len(bbox_dicts),
                'bboxes': bbox_dicts,
                'griddata': griddata
            }
        else:
            position_dicts = []
            for position in detects:
                position_dict = {
                    'x': position[0],
                    'y': position[1]
                    }
                position_dicts.append(position_dict)

            result_dict = {
                'number_of_detects': len(position_dicts),
                'positiones': position_dicts,
                'griddata': griddata
            }

        return result_dict


    def get_param_info(self):
        """get parameter for other process

        """

        return self._param


    def _set_queue(self,data):
        """Set input data in queue

        """
        self._queue.put(data)

    def _get_queue(self):
        """Get data from queue

        """
        return self._queue.get()


    def _calc_distance(self, base_h, base_v, point_h, point_v):
        """Distance calculation from center coordinates

        """
        base = np.array([base_h,base_v])
        point = np.array([point_h,point_v])
        distance = np.linalg.norm(base - point)

        return distance

    def _pix_to_grid(self, in_h, in_v):
        """Coordinate to grid conversion

        """
        grid_pos_h = in_h // self._param['grid_size_h']
        grid_pos_v = in_v // self._param['grid_size_v']
        return grid_pos_h, grid_pos_v


    def _dec_around_grid(self, pos_h, pos_v):
        """Subtract peripheral pixels

        """
        if self._number_of_add_grid    > 0:
            for h_g in range(
                pos_h - self._number_of_add_grid , pos_h + self._number_of_add_grid):
                for v_g in range(
                    pos_v - self._number_of_add_grid , pos_v + self._number_of_add_grid):
                    if(0 <= h_g < self._param['grid_num_h']) \
                        and (0 <= v_g < self._param['grid_num_v']):
                        if self._calc_distance(pos_h,pos_v,h_g,v_g) \
                            <= self._number_of_add_grid :
                            self._griddata[v_g][h_g] -= 1
        else:
            self._griddata[pos_v][pos_h] -= 1

    def _add_around_grid(self, pos_h, pos_v):
        """Add peripheral pixels

        """
        if self._number_of_add_grid    > 0:
            for h_g in range(
                pos_h - self._number_of_add_grid , pos_h + self._number_of_add_grid):
                for v_g in range(
                    pos_v - self._number_of_add_grid , pos_v + self._number_of_add_grid):
                    if(0 <= h_g < self._param['grid_num_h']) \
                        and (0 <= v_g < self._param['grid_num_v']):
                        if self._calc_distance(pos_h,pos_v,h_g,v_g) \
                            <= self._number_of_add_grid :
                            self._griddata[v_g][h_g] += 1
        else:
            self._griddata[pos_v][pos_h] += 1

    def _dec_bbox(self, data):
        """
        bbox[0] Left
        bbox[1] Top
        bbox[2] Right
        bbox[3] Bottom
        """
        for bbox in data:
            grid_l, grid_t = self._pix_to_grid(bbox[0], bbox[1])
            grid_r, grid_b = self._pix_to_grid(bbox[2], bbox[3])
            grid_l = max(grid_l - self._number_of_add_grid, 0)
            grid_t = max(grid_t - self._number_of_add_grid, 0)
            grid_l = min(grid_l, self._param['grid_num_h'] - 1)
            grid_t = min(grid_t, self._param['grid_num_v'] - 1)
            grid_r = min(
                grid_r + self._number_of_add_grid, self._param['grid_num_h'] - 1)
            grid_b = min(
                grid_b + self._number_of_add_grid, self._param['grid_num_v'] - 1)
            for h_g in range(grid_l, grid_r):
                for v_g in range(grid_t, grid_b):
                    self._griddata[v_g][h_g] -= 1

    def _add_bbox(self, data):
        """
        bbox[0] Left
        bbox[1] Top
        bbox[2] Right
        bbox[3] Bottom
        """
        for bbox in data:
            grid_l, grid_t = self._pix_to_grid(bbox[0], bbox[1])
            grid_r, grid_b = self._pix_to_grid(bbox[2], bbox[3])
            grid_l = max(grid_l - self._number_of_add_grid, 0)
            grid_t = max(grid_t - self._number_of_add_grid, 0)
            grid_l = min(grid_l, self._param['grid_num_h'] - 1)
            grid_t = min(grid_t, self._param['grid_num_v'] - 1)
            grid_r = min(
                grid_r + self._number_of_add_grid, self._param['grid_num_h'] - 1)
            grid_b = min(
                grid_b + self._number_of_add_grid, self._param['grid_num_v'] - 1)
            for h_g in range(grid_l, grid_r):
                for v_g in range(grid_t, grid_b):
                    self._griddata[v_g][h_g] += 1


    def _bbox_to_point(self,bboxes):
        """Convert bbox to coordinates

        """
        positiones = []
        ratio = self._bbox2pix_ratio
        for bbox in bboxes:
            position = [
                int((bbox[0] + bbox[2])/2.0),
                int(bbox[1]*(1.0-ratio) + bbox[3]*ratio)
            ]
            positiones.append(position)
        return positiones
