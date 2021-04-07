import abc
import logging

import pandas as pd

import instrument_master.common.data.types as vcdtyp

_LOG = logging.getLogger(__name__)


class AbstractS3ToSqlTransformer(abc.ABC):
    @classmethod
    def transform(
        cls,
        df: pd.DataFrame,
        trade_symbol_id: int,
        frequency: vcdtyp.Frequency,
    ) -> pd.DataFrame:
        """
        Transform data stored on S3 to load to SQL.

        :param df: dataframe with data from S3
        :param trade_symbol_id: symbol id in SQL database
        :param frequency: dataframe frequency
        :return: processed dataframe
        """