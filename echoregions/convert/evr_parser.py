import pandas as pd
import json
from collections import defaultdict
from .ev_parser import EvParserBase
import os
import echopype as ep
from .utils import parse_time


class Region2DParser(EvParserBase):
    def __init__(self, input_files=None):
        super().__init__()
        self.format = 'EVR'
        self.input_files = input_files
        self._raw_range = None
        self._min_depth = None
        self._max_depth = None

    @property
    def max_depth(self):
        return self._max_depth

    @property
    def min_depth(self):
        return self._min_depth

    @max_depth.setter
    def max_depth(self, val):
        if self._min_depth is not None:
            if val <= self._min_depth:
                raise ValueError("max_depth cannot be less than min_depth")
        self._max_depth = val

    @min_depth.setter
    def min_depth(self, val):
        if self._max_depth is not None:
            if val >= self._max_depth:
                raise ValueError("min_depth cannot be greater than max_depth")
        self._min_depth = val

    def _parse(self, fid, convert_range_edges):
        """Reads an open file and returns the file metadata and region information"""
        def _region_metadata_to_dict(line):
            """Assigns a name to each value in the metadata line for each region"""
            return {
                'structure_version': line[0],                               # 13 currently
                'point_count': line[1],                                     # Number of points in the region
                'selected': line[3],                                        # Always 0
                'creation_type': line[4],                                   # Described here: https://support.echoview.com/WebHelp/Reference/File_formats/Export_file_formats/2D_Region_definition_file_format.htm#Data_formats
                'dummy': line[5],                                           # Always -1
                'bounding_rectangle_calculated': line[6],                   # 1 if next 4 fields valid. O otherwise
                # Date encoded as CCYYMMDD and times in HHmmSSssss
                # Where CC=Century, YY=Year, MM=Month, DD=Day, HH=Hour, mm=minute, SS=second, ssss=0.1 milliseconds
                'bounding_rectangle_left_x': f'D{line[7]}T{line[8]}',       # Time and date of bounding box left x
                'bounding_rectangle_top_y': line[9],                       # Top of bounding box
                'bounding_rectangle_right_x': f'D{line[10]}T{line[11]}',    # Time and date of bounding box right x
                'bounding_rectangle_bottom_y': line[12],                    # Bottom of bounding box
            }

        def _points_to_dict(line):
            """Takes a line with point information and creates a tuple (x, y) for each point"""
            points = {}
            for point_num, idx in enumerate(range(0, len(line), 3)):
                x = f'D{line[idx]}T{line[idx + 1]}'
                y = line[idx + 2]
                if convert_range_edges:
                    if y == '9999.9900000000' and self.max_depth is not None:
                        y = float(self.max_depth)
                    elif y == '-9999.9900000000' and self.min_depth is not None:
                        y = float(self.min_depth)

                points[point_num] = [x, y]
            return points

        # Read header containing metadata about the EVR file
        filetype, file_format_number, echoview_version = self.read_line(fid, True)
        file_metadata = {
            'filetype': filetype,
            'file_format_number': file_format_number,
            'echoview_version': echoview_version
        }

        regions = defaultdict(dict)
        n_regions = int(self.read_line(fid))
        # Loop over all regions in file
        for r in range(n_regions):
            fid.readline()    # blank line separates each region
            region_metadata = self.read_line(fid, True)
            rid = region_metadata[2]        # Region ID (unique for each region)

            regions[rid]['metadata'] = _region_metadata_to_dict(region_metadata)
            # Add notes to region data
            n_note_lines = int(self.read_line(fid))
            regions[rid]['notes'] = [self.read_line(fid) for l in range(n_note_lines)]
            # Add detection settings to region data
            n_detection_setting_lines = int(self.read_line(fid))
            regions[rid]['detection_settings'] = [self.read_line(fid) for l in range(n_detection_setting_lines)]
            # Add classification to region data
            regions[rid]['metadata']['region_classification'] = self.read_line(fid)
            # Add point x and y
            points_line = self.read_line(fid, True)
            # For type: 0=bad (No data), 1=analysis, 3=fishtracks, 4=bad (empty water)
            regions[rid]['metadata']['type'] = points_line.pop()
            regions[rid]['points'] = _points_to_dict(points_line)
            regions[rid]['metadata']['name'] = self.read_line(fid)

        return file_metadata, regions

    def to_csv(self, save_dir=None, **kwargs):
        """Convert an Echoview 2D regions .evr file to a .csv file

        Parameters
        ----------
        save_dir : str
            directory to save the CSV file to
        """
        # Parse EVR file if it hasn't already been done
        if not self.output_data:
            self.parse_files(**kwargs)
        # Check if the save directory is safe
        save_dir = self._validate_path(save_dir)
        row = []

        # Loop over each file. 1 EVR file is saved to 1 CSV file
        for file, data, in self.output_data.items():
            df = pd.DataFrame()
            # Save file metadata for each point
            metadata = pd.Series(data['metadata'])
            # Loop over each region
            for rid, region in data['regions'].items():
                # Save region information for each point
                region_metadata = pd.Series(region['metadata'])
                region_notes = pd.Series({'notes': region['notes']})
                detection_settings = pd.Series({'detection_settings': region['detection_settings']})
                region_id = pd.Series({'region_id': rid})
                # Loop over each point in each region. One row of the dataframe corresponds to one point
                for p, point in enumerate(region['points'].values()):
                    point = pd.Series({
                        'point_idx': p,
                        'x': point[0],
                        'y': point[1],
                    })
                    row = pd.concat([region_id, point, metadata, region_metadata, region_notes, detection_settings])
                    df = df.append(row, ignore_index=True)
            # Reorder columns and export to csv
            output_file_path = os.path.join(save_dir, file) + '.csv'
            df[row.keys()].to_csv(output_file_path, index=False)
            self._output_path.append(output_file_path)

    def get_points_from_region(self, region, file, convert_time=False):
        """Get points from specified region from a JSON or CSV file
        or from the parsed data.

        Parameters
        ----------
        region : int
            ID of the region to extract points from
        file : str
            path to JSON or CSV file or the filename of
            the original EVR file. (Key of `self.output_data`)
        convert_time : bool
            whether or not to convert the EV timestamps to datetime64

        Returns
        -------
        points : list
            list of x, y points
        """
        # Pull region points from CSV file
        if file.upper().endswith('.CSV'):
            if not os.path.isfile(file):
                raise ValueError(f"{file} is not a valid CSV file.")
            data = pd.read_csv(file)
            region = data.loc[data['region_id'] == int(region)]
            # Combine x and y points to get a list of tuples
            return list(zip(region.x, region.y))
        # Pull region points from JSON or Parsed data (similar dict structure)
        else:
            # JSON file
            if file.upper().endswith('.JSON'):
                if not os.path.isfile(file):
                    raise ValueError(f"{file} is not a valid JSON file.")
                with open(file) as f:
                    data = json.load(f)
            # Parsed data
            else:
                data = self.output_data[file]
            # Navigate the tree structure and get the points as a list of lists
            points = list(data['regions'][str(region)]['points'].values())
            if convert_time:
                for p in points:
                    p[0] = parse_time(p[0])
            # Convert to a list of tuples for consistency with CSV
            return [list(l) for l in points]

    def set_range_edge_from_raw(self, raw=None, model='EK60'):
        """Calculate the sonar range from a raw file using Echopype.
        Used to replace EVR range edges -9999.99 and 9999.99 with real values

        Parameters
        ----------
        raw : str
            Path to raw file
        model : str
            The sonar model that created the raw file, defaults to `EK60`.
            See echopype for list of supported sonar models
        """
        if raw is not None:
            if raw.endswith('.raw') and os.path.isfile(raw):
                tmp_c = ep.Convert(raw, model='EK60')
                tmp_c.to_netcdf(save_path='./')

                ed = ep.process.EchoData(tmp_c.output_file)
                proc = ep.process.Process('EK60', ed)

                # proc.get_range # Calculate range directly as opposed to with get_Sv
                proc.get_Sv(ed)
                self._raw_range = ed.range.isel(frequency=0, ping_time=0).load()

                self.max_depth = self._raw_range.max().values
                self.min_depth = self._raw_range.min().values

                ed.close()
                os.remove(tmp_c.output_file)
            else:
                raise ValueError("Invalid raw file")
