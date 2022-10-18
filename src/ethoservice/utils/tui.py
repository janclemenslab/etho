import rich
from rich.panel import Panel
from rich.console import Console
from rich.table import Table
from typing import Optional
import pandas as pd
import time


def dict_to_def(d):
    s = ''
    for key, val in d.items():
        s += f"[bold]{key}[/]:\n   {str(val)}\n"
    return s


def dict_to_def_aults(d, d2):
    s = ''
    for key, val in d.items():
        s += f"[bold]{key}[/]:\n   {str(val)}"
        if key in d2:
            s += f" (target: {str(d2[key])})"
        s += '\n'
    return s


def dict_to_table(d, title=None, key_name='Key', value_names=None):

    table = Table(title=title)

    table.add_column(key_name, justify="right", style="cyan", no_wrap=True)
    if value_names is None:
        first_key = list(d.keys())[0]
        value_names = [f'Value {cnt}' for cnt, _ in enumerate(d[first_key])]

    for value_name in value_names:
        table.add_column(value_name, justify='left', style="magenta")

    for key, val in d.items():
        table.add_row(key, *[str(v) for v in val])
    return table


def df_to_table(
    pandas_dataframe: pd.DataFrame,
    rich_table: Table,
    show_index: bool = True,
    index_name: Optional[str] = None,
) -> Table:
    """Convert a pandas.DataFrame obj into a rich.Table obj.
    Args:
        pandas_dataframe (DataFrame): A Pandas DataFrame to be converted to a rich Table.
        rich_table (Table): A rich Table that should be populated by the DataFrame values.
        show_index (bool): Add a column with a row count to the table. Defaults to True.
        index_name (str, optional): The column name to give to the index column. Defaults to None, showing no value.
    Returns:
        Table: The rich Table instance passed, populated with the DataFrame values."""

    if show_index:
        index_name = str(index_name) if index_name else ""
        rich_table.add_column(index_name)

    for column in pandas_dataframe.columns:
        rich_table.add_column(str(column))

    for index, value_list in enumerate(pandas_dataframe.values.tolist()):
        row = [str(index)] if show_index else []
        row += [str(x) for x in value_list]
        rich_table.add_row(*row)

    return rich_table


class CameraProgress():

    def __init__(self, nbFrames: int):
        self.prev_t: Optional[float] = None
        self.prev_n: Optional[int] = None
        self.console = Console()
        self.nbFrames = nbFrames
        self.nDigits = len(str(int(self.nbFrames)))

    def update(self, number_of_frames: int, payload=None):
        t = time.time()
        if self.prev_t is not None:
            current_frame_interval = (t - self.prev_t) / (number_of_frames - self.prev_n)
            current_frame_rate = 1 / current_frame_interval

            prgrs_len = self.console.size.width // 2 - 40
            prgrs_cut = round(number_of_frames / (self.nbFrames // prgrs_len))

            prgrs = []
            for pos in range(prgrs_len):
                if pos < prgrs_cut:
                    prgrs.append('█')
                else:
                    prgrs.append('░')

            progressbar = f"\rCamera: [{''.join(prgrs)}] {int(number_of_frames): {self.nDigits}d}/{self.nbFrames} frames at {current_frame_rate:1.2f} fps    "
            if payload is not None:
                progressbar += f"{payload}"
            print(progressbar, end='')
        self.prev_t = t
        self.prev_n = number_of_frames
