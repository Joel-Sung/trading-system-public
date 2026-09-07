import pandas as pd


def does_df_contain_cols(df: pd.DataFrame, required_cols: list[str]) -> bool:
    for col in required_cols:
        if col not in df.columns:
            return False
    return True
