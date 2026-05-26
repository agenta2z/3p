from typing import Callable

from pyspark.sql import DataFrame
import tqdm
from python_utils.io_utils.json_io import write_json
from python_utils.spark_utils.parallel_compute import parallel_compute


def ner_spark_batch(
        df_text: DataFrame,
        text_field_name: str,
        ner_result_field_name: str,
        output_path: str,
        repartition: int,
        ner: Callable = None,
        ner_batch: Callable = None
):
    def compute_pos_tags(partition, meta_data_compute=None):
        if ner_batch is not None:
            texts = [
                row[text_field_name]
                for row in
                tqdm.tqdm(partition, desc='cacheing partition texts')
            ]
            out = []
            for text, ner_result in zip(texts, ner_batch(texts)):
                out.append({
                    text_field_name: text,
                    ner_result_field_name: ner_result
                })

            return out
        elif ner is not None:
            out = []
            for row in tqdm.tqdm(partition, desc='ner partition texts'):
                text = row[text_field_name]
                out.append({
                    text_field_name: text,
                    ner_result_field_name: ner(text)
                })
        else:
            raise ValueError(f"one of 'ner' or 'ner_batch' must be specified")

    return parallel_compute(
        df=df_text,
        partition_transform_func=compute_pos_tags,
        combine_partition_transform_func=None,
        repartition=repartition,
        file_based_combine=True,
        output_result_to_files=True,
        output_path=output_path,
        output_overwrite=True,
        output_write_func=write_json,
        output_file_pattern='{}.json'
    )
