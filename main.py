# main.py
from pathlib import Path
from preprocessing.preprocess_all_raw_datasets import preprocess_all

preprocess_all(root_path=Path(__file__).resolve().parent)