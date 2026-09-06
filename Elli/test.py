import os
import pandas as pd
from docx import Document
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
RANDOM_SEED = 42
def add_clustering(df: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [
        "algorithm_score", "function_score", "main_score", "structure_score",
        "syntax_error_int", "runtime_error_int", "input_count", "print_count",
        "has_function", "has_return", "has_if", "has_loop", "has_list",
        "has_modulo", "has_append", "has_comprehension", "code_length", "line_count",
    ]
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0

    if len(df) < 3:
        df["cluster"] = "λίγα δεδομένα"
        df["cluster_description"] = "Δεν υπάρχουν αρκετές υποβολές για clustering."
        return df

    X = df[feature_cols].fillna(0)
    X_scaled = StandardScaler().fit_transform(X)
    k = min(3, len(df))
    model = KMeans(n_clusters=k, random_state=RANDOM_SEED, n_init=10)
    labels = model.fit_predict(X_scaled)
    df["cluster"] = labels

    descriptions = {}
    for c in sorted(set(labels)):
        sub = df[df["cluster"] == c]
        avg_alg = sub["algorithm_score"].mean()
        avg_func = sub["function_score"].mean() if "function_score" in sub else 0
        avg_main = sub["main_score"].mean() if "main_score" in sub else 0
        if avg_alg >= 85:
            desc = "Ομάδα ισχυρών λύσεων"
        elif avg_func >= 80 and avg_main < 70:
            desc = "Ομάδα με σωστή συνάρτηση αλλά αδυναμία στο κύριο πρόγραμμα/input-output"
        elif avg_alg >= 55:
            desc = "Ομάδα με μερική κατανόηση και διορθώσιμα λάθη"
        else:
            desc = "Ομάδα υψηλής ανάγκης υποστήριξης"
        descriptions[c] = desc
    df["cluster_description"] = df["cluster"].map(descriptions)
    return df
LOCAL_AGENT_MODEL = os.getenv("LOCAL_AGENT_MODEL", "Qwen/Qwen2.5-Coder-1.5B-Instruct", )
rows = [] ; results = pd.DataFrame(rows)
results = add_clustering(results)
print(results)