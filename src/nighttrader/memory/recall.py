"""Semantic recall over the decision/news log — embeddings-in-parquet with
brute-force cosine search (RT-10). At hobby scale (thousands of rows) this is
simpler and fast enough; graduate to Qdrant only when it is measurably slow.
Keep the row schema stable so a migration is a bulk copy, not a rewrite.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EMBEDDING_COL = "embedding"


def cosine_top_k(
    query_vec: np.ndarray,
    corpus: pd.DataFrame,
    k: int = 5,
) -> pd.DataFrame:
    """Rows of ``corpus`` most similar to ``query_vec``.

    ``corpus[EMBEDDING_COL]`` holds list[float] per row (as stored in
    parquet). Returns top-k rows with a ``similarity`` column, best first.
    """
    if corpus.empty:
        return corpus.assign(similarity=pd.Series(dtype=float))
    mat = np.vstack(corpus[EMBEDDING_COL].to_numpy())
    q = np.asarray(query_vec, dtype=float)
    denom = np.linalg.norm(mat, axis=1) * np.linalg.norm(q)
    denom[denom == 0] = np.inf
    sims = mat @ q / denom
    out = corpus.assign(similarity=sims).sort_values("similarity", ascending=False)
    return out.head(k)
