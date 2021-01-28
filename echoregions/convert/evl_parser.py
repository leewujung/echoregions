import pandas as pd
import os
from .ev_parser import EvParserBase
from .utils import parse_time


class LineParser(EvParserBase):
    def __init__(self, input_files=None):
        super().__init__()
        self.format = 'EVL'
        self.input_files = input_files

    def _parse(self, fid, replace_nan_range_value=None):
        # Read header containing metadata about the EVL file
        filetype, file_format_number, ev_version = self.read_line(fid, True)
        file_metadata = {
            'filetype': filetype,
            'file_format_number': file_format_number,
            'echoview_version': ev_version
        }
        points = {}
        n_points = int(self.read_line(fid))
        for i in range(n_points):
            date, time, depth, status = self.read_line(fid, split=True)
            if replace_nan_range_value is not None and depth == '-10000.990000':
                depth = replace_nan_range_value
            points[i] = {
                'x': f'D{date}T{time}',           # Format: D{CCYYMMDD}T{HHmmSSssss}
                'y': depth,                           # Depth [m]
                'status': status                      # 0 = none, 1 = unverified, 2 = bad, 3 = good
            }
        return file_metadata, points

    def to_csv(self, save_dir=None):
        """Convert an Echoview lines .evl file to a .csv file

        Parameters
        ----------
        save_dir : str
            directory to save the CSV file to
        """
        if not self.output_data:
            self.parse_files()

        # Check if the save directory is safe
        save_dir = self._validate_path(save_dir)

        # Loop over each file. 1 EVL file is saved to 1 CSV file
        for file, data, in self.output_data.items():
            # Save a row for each point
            df = pd.concat(
                [pd.DataFrame([point], columns=['x', 'y', 'status']) for
                 pid, point in data['points'].items()],
                ignore_index=True
            )
            # Save file metadata for each point
            metadata = pd.Series(data['metadata'])
            for k, v in metadata.items():
                df[k] = v

            # Reorder columns and export to csv
            output_file_path = os.path.join(save_dir, file) + '.csv'
            df.to_csv(output_file_path, index=False)
            self._output_path.append(output_file_path)

    def JSON_to_dict(self, j, convert_time=True, replace_nan_range_value=None):
        """Convert JSON to dict

        Parameters
        ----------
        j : str
            Valid JSON string or path to JSON file
        convert_time : bool
            Whether to convert EV time to datetime64, defaults to `True`
        replace_nan_range_value : bool
            Value to replace -10000.990000 ranges with.
            Don't replace if `None`

        Returns
        -------
        data : dict
            dicationary from JSON data

        Raises
        ------
        ValueError
            when j is not a valid echoregions JSON file or JSON string
        """

        data_dict = self.from_JSON(j)

        if convert_time or replace_nan_range_value is not None:
            if 'points' not in data_dict:
                raise ValueError("Invalid data format")

            for point in data_dict['points'].values():
                if convert_time:
                    point['x'] = parse_time(point['x'])
                if replace_nan_range_value is not None and point['y'] == '-10000.990000':
                    point['y'] = replace_nan_range_value

        return data_dict
