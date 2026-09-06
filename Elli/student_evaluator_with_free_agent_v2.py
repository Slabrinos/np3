import ast
import contextlib
import glob
import io
import os
import random
import re
import argparse
import pandas as pd

from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import patch
from docx import Document
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

#from pedagogyOpenAI import FreePedagogicalAgent
from pedagogyGemini import FreePedagogicalAgent
from pedagogyGemini3Agents import BeginnerScaffoldingAgent
from pedagogyGemini3Agents import CodeOptimizationAgent
from pedagogyGemini3Agents import SocraticDebuggingAgent
from evaluator import (
    needs_pedagogical_feedback,
    empty_pedagogical_feedback,
    fallback_pedagogical_feedback,
)
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
DEFAULT_EXCEL_FILE = "students_code45.xlsx"
DEFAULT_WORD_FILE = "week12.docx"
OUTPUT_FILE = "results_week_v5_resources.xlsx"
VIDEO_FILE = "videos.csv"
DEFAULT_VIDEO_URL = "https://youtu.be/K5KVEU3aaeQ"
DEFAULT_VIDEO_TITLE = "Βασική σύνταξη Python"
DEFAULT_BOOK_TITLE = "Παιχνίδια σε Python & Pygame"
COLUMN_KEYWORDS = {
    "student_id": ["student_id", "student", "userid", "user id", "full name", "fullname", "name", "όνομα", "email"],
    "email": ["email", "email address", "mail"],
    "group": ["group", "ομάδα", "ομαδα"],
    "code": ["code", "κώδικας", "κωδικας", "submission", "answer", "response", "online text", "text", "υποβολή", "υποβολη", "απάντηση", "απαντηση"],
    "week": ["week", "εβδομάδα", "εβδομαδα", "βδομάδα", "βδομαδα"],
    "grade": ["grade", "score", "mark", "βαθμός", "βαθμος", "final grade", "grade/100"],
    "attendance": ["attendance", "presence", "παρουσία", "παρουσια", "απουσίες", "απουσιες"],
}
# Κάθε κατηγορία μπορεί να συνδεθεί με ξεχωριστό υλικό αργότερα.
# Προς το παρόν δίνουμε πιλοτικά ίδιο υλικό όπου δεν υπάρχει πιο ειδική εγγραφή.
RESOURCE_CATEGORY_KEYWORDS = {
    "syntax": ["syntax", "invalid syntax", "σύνταξη", "συντακτικό"],
    "indentation": ["indentation", "indent", "εσοχή", "tabs", "spaces"],
    "parentheses": ["parentheses", "brackets", "παρένθεση", "αγκύλη"],
    "colon": ["colon", "άνω-κάτω", "if", "for", "while", "def"],
    "string": ["string", "quotes", "εισαγωγικά", "συμβολοσειρές"],
    "semicolon": ["semicolon", "ερωτηματικό"],
    "condition_operator": ["condition", "operator", "==", "="],
    "empty_code": ["empty", "κενό", "υποβολή"],
    "runtime_error": ["runtime", "debugging", "error"],
    "function_missing": ["function", "def", "συνάρτηση"],
    "return_missing": ["return", "επιστρέφει"],
    "wrong_function_name": ["function name", "evenlist", "όνομα συνάρτησης"],
    "logic_even_filter": ["even", "άρτι", "modulo", "%"],
    "input_output": ["input", "output", "print", "είσοδος", "έξοδος"],
    "list_handling": ["list", "λίστα", "append"],
    "algorithm": ["algorithm", "αλγόριθμος", "λογική"],
}
# ============================================================
# ΒΟΗΘΗΤΙΚΑ ΑΡΧΕΙΩΝ
# ============================================================

def find_file(preferred: str, pattern: str) -> str:
    if os.path.exists(preferred):
        return preferred
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"Δεν βρέθηκε αρχείο: {preferred} ή pattern {pattern}")
    return matches[0]
def find_excel_file_for_week(target_week: Optional[int]) -> Tuple[str, str]:
    """
    Επιλέγει αυτόματα το σωστό Excel υποβολών.
    Δεν παίρνει τυφλά το πρώτο .xlsx, γιατί μπορεί να βρει παλιό results.xlsx.
    Προτιμά αρχείο που έχει στήλες/περιεχόμενο υποβολών και περιέχει τη ζητούμενη εβδομάδα.
    Επιστρέφει (excel_path, diagnostic_message).
    """
    candidates = []

    # Προτιμά το DEFAULT αν υπάρχει, αλλά ελέγχει και όλα τα υπόλοιπα .xlsx.
    if os.path.exists(DEFAULT_EXCEL_FILE):
        candidates.append(DEFAULT_EXCEL_FILE)

    for f in sorted(glob.glob("*.xlsx")):
        base = os.path.basename(f).lower()
        if f not in candidates:
            candidates.append(f)

    # Αγνόησε αρχεία αποτελεσμάτων, εκτός αν δεν υπάρχει τίποτα άλλο.
    preferred_candidates = [
        f for f in candidates
        if not os.path.basename(f).lower().startswith(("results", "syntax_results"))
    ] or candidates

    diagnostics = []
    valid_without_week_match = []

    for f in preferred_candidates:
        try:
            temp_df, temp_mapping = load_submissions(f)
        except Exception as exc:
            diagnostics.append(f"{f}: δεν διαβάστηκε ως Excel υποβολών ({exc})")
            continue

        available_weeks = sorted(temp_df["week"].dropna().astype(int).unique().tolist())
        diagnostics.append(f"{f}: διαθέσιμες εβδομάδες {available_weeks}, στήλες {temp_mapping}")

        if target_week is None:
            return f, "Δεν δόθηκε target week· επιλέχθηκε το πρώτο έγκυρο Excel. " + " | ".join(diagnostics)

        if target_week in available_weeks:
            return f, "Επιλέχθηκε Excel που περιέχει τη ζητούμενη εβδομάδα. " + " | ".join(diagnostics)

        valid_without_week_match.append((f, available_weeks))

    diagnostic_message = "Δεν βρέθηκε Excel με υποβολές για την εβδομάδα " + str(target_week) + ". " + " | ".join(diagnostics)
    raise ValueError(diagnostic_message)
def read_docx_text(path: str) -> str:
    doc = Document(path)
    parts = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            parts.append(text)
    return "\n".join(parts)
def detect_week_from_filename_or_text(word_path: str, text: str) -> Optional[int]:
    source = f"{os.path.basename(word_path)}\n{text}".lower()
    patterns = [
        r"week\s*[_-]?\s*(\d+)",
        r"εβδομ(?:ά|α)δα\s*[_-]?\s*(\d+)",
        r"βδομ(?:ά|α)δα\s*[_-]?\s*(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, source, flags=re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None
# ============================================================
# ΑΝΑΓΝΩΣΗ EXCEL ΚΑΙ ΕΝΤΟΠΙΣΜΟΣ ΣΤΗΛΩΝ
# ============================================================
def find_column(df: pd.DataFrame, keys: List[str]) -> Optional[str]:
    for col in df.columns:
        c = str(col).strip().lower()
        for key in keys:
            if key.lower() in c:
                return col
    return None
def looks_like_python_code(value: Any) -> bool:
    if pd.isna(value):
        return False
    text = str(value)
    patterns = ["input(", "print(", "def ", "return", "if ", "elif ", "else:", "for ", "while ", "len(", "range(", "=", "list(", "dict("]
    return any(p in text for p in patterns)
def detect_code_column_by_content(df: pd.DataFrame) -> Optional[str]:
    best_col = None
    best_score = 0
    for col in df.columns:
        score = int(df[col].apply(looks_like_python_code).sum())
        if score > best_score:
            best_score = score
            best_col = col
    return best_col if best_score > 0 else None
def clean_grade(value: Any) -> Optional[float]:
    if pd.isna(value):
        return None
    txt = str(value).replace(",", ".")
    nums = re.findall(r"\d+(?:\.\d+)?", txt)
    if not nums:
        return None
    try:
        return float(nums[0])
    except ValueError:
        return None
def normalize_week(value: Any) -> Optional[int]:
    if pd.isna(value):
        return None
    m = re.search(r"\d+", str(value))
    return int(m.group(0)) if m else None
def load_submissions(excel_path: str) -> Tuple[pd.DataFrame, Dict[str, str]]:
    raw = pd.read_excel(excel_path)
    raw.columns = [str(c).strip() for c in raw.columns]

    mapping = {
        "student_id": find_column(raw, COLUMN_KEYWORDS["student_id"]),
        "email": find_column(raw, COLUMN_KEYWORDS["email"]),
        "group": find_column(raw, COLUMN_KEYWORDS["group"]),
        "code": find_column(raw, COLUMN_KEYWORDS["code"]),
        "week": find_column(raw, COLUMN_KEYWORDS["week"]),
        "grade": find_column(raw, COLUMN_KEYWORDS["grade"]),
        "attendance": find_column(raw, COLUMN_KEYWORDS["attendance"]),
    }

    if mapping["code"] is None:
        mapping["code"] = detect_code_column_by_content(raw)

    if mapping["student_id"] is None:
        mapping["student_id"] = raw.columns[0]

    missing = []
    if mapping["code"] is None:
        missing.append("στήλη κώδικα")
    if mapping["week"] is None:
        missing.append("στήλη εβδομάδας/week")
    if missing:
        raise ValueError("Δεν βρέθηκαν απαιτούμενες στήλες: " + ", ".join(missing))

    df = pd.DataFrame()
    df["student_id"] = raw[mapping["student_id"]]
    df["email"] = raw[mapping["email"]] if mapping["email"] else ""
    df["group"] = raw[mapping["group"]] if mapping["group"] else ""
    df["code"] = raw[mapping["code"]].astype(str)
    df["week"] = raw[mapping["week"]].apply(normalize_week)
    df["grade"] = raw[mapping["grade"]] if mapping["grade"] else None
    df["grade_numeric"] = df["grade"].apply(clean_grade)
    df["attendance"] = raw[mapping["attendance"]] if mapping["attendance"] else None

    df = df.dropna(subset=["code", "week"]).reset_index(drop=True)
    df["week"] = df["week"].astype(int)
    return df, {k: str(v) for k, v in mapping.items() if v is not None}
# ============================================================
# ΕΚΦΩΝΗΣΗ
def detect_exercise_type(text: str) -> str:
    t = text.lower()
    if "evenlist" in t or "άρτι" in t or "αρτι" in t or "ζυγ" in t:
        return "evenlist"
    if "παλίνδρο" in t or "παλινδρο" in t or "palindrome" in t:
        return "palindrome"
    return "generic_python"
def infer_requirements(text: str) -> Dict[str, int]:
    t = text.lower()
    return {
        "requires_function": int(any(x in t for x in ["συνάρτηση", "function", "def", "evenlist"])),
        "requires_input": int(any(x in t for x in ["input", "διαβάζει", "εισαγωγή", "εισαγωγη", "πληκτρολογεί", "χρήστης"])),
        "requires_print": int(any(x in t for x in ["print", "εμφανίζει", "εμφανιζει", "εκτυπώνει", "εκτυπωνει"])),
        "requires_list": int(any(x in t for x in ["λίστα", "λιστα", "λίστες", "λιστες", "list"])),
        "requires_dict": int(any(x in t for x in ["λεξικό", "λεξικο", "dictionary", "dict"])),
        "requires_if": int(any(x in t for x in ["αν ", "if", "ελέγχει", "ελεγχει", "συνθήκη", "συνθηκη"])),
        "requires_loop": int(any(x in t for x in ["επανάληψη", "επαναληψη", "for", "while"])),
    }
# ============================================================
# ΠΡΟΧΩΡΗΜΕΝΟΣ ΣΥΝΤΑΚΤΙΚΟΣ ΕΛΕΓΧΟΣ
# ============================================================
def classify_syntax_error(error_message: str, code_line: str) -> Tuple[str, str]:
    msg = str(error_message).lower()
    line = str(code_line).strip()

    if "expected ':'" in msg:
        return "colon", "Λείπει άνω-κάτω τελεία ':' μετά από if/for/while/def."
    if "unexpected indent" in msg:
        return "indentation", "Υπάρχει λανθασμένη εσοχή/indentation."
    if "expected an indented block" in msg:
        return "indentation", "Λείπει εσοχή μετά από if/for/while/def."
    if "unindent does not match" in msg:
        return "indentation", "Οι εσοχές δεν είναι συνεπείς."
    if "inconsistent use of tabs and spaces" in msg:
        return "indentation", "Έχουν αναμειχθεί tabs και spaces."
    if "was never closed" in msg or "unexpected eof" in msg:
        return "parentheses", "Δεν έχει κλείσει σωστά παρένθεση, αγκύλη ή εισαγωγικό."
    if "unterminated string" in msg or "eol while scanning string" in msg:
        return "string", "Δεν έχει κλείσει σωστά το string με εισαγωγικά."
    if "invalid syntax" in msg:
        if ";" in line or ";" in line:
            return "semicolon", "Πιθανή λάθος χρήση ελληνικού ή λατινικού ερωτηματικού/semicolon."
        if re.search(r"\bif\b.*[^=!<>]=[^=]", line):
            return "condition_operator", "Πιθανή χρήση '=' αντί για '==' μέσα σε συνθήκη."
        return "syntax", "Γενικό συντακτικό λάθος."
    return "syntax", "Συντακτικό λάθος που χρειάζεται διόρθωση."
def check_syntax_detailed(code: str) -> Dict[str, Any]:
    code = "" if code is None else str(code)

    if not code.strip() or code.strip().lower() in ["nan", "none"]:
        return {
            "syntax_error": True,
            "syntax_error_type": "EmptyCode",
            "syntax_error_line": "",
            "syntax_error_message": "Δεν υπάρχει κώδικας προς έλεγχο.",
            "syntax_error_category": "empty_code",
            "syntax_explanation": "Ο φοιτητής δεν υπέβαλε κώδικα."
        }

    try:
        ast.parse(code)
        return {
            "syntax_error": False,
            "syntax_error_type": "",
            "syntax_error_line": "",
            "syntax_error_message": "",
            "syntax_error_category": "",
            "syntax_explanation": "Δεν εντοπίστηκε συντακτικό λάθος."
        }

    except (IndentationError, TabError, SyntaxError) as e:
        lines = code.splitlines()
        line_text = ""
        if getattr(e, "lineno", None):
            idx = e.lineno - 1
            if 0 <= idx < len(lines):
                line_text = lines[idx]

        category, explanation = classify_syntax_error(getattr(e, "msg", str(e)), line_text)

        return {
            "syntax_error": True,
            "syntax_error_type": type(e).__name__,
            "syntax_error_line": getattr(e, "lineno", ""),
            "syntax_error_message": getattr(e, "msg", str(e)),
            "syntax_error_category": category,
            "syntax_explanation": explanation
        }
# Backward-compatible helper.
def check_syntax(code: str) -> Tuple[bool, str]:
    result = check_syntax_detailed(code)
    if result["syntax_error"]:
        return True, f"{result['syntax_error_type']} στη γραμμή {result['syntax_error_line']}: {result['syntax_error_message']}"
    return False, ""
# ============================================================
# AST ΚΑΙ ΑΣΦΑΛΗΣ ΕΚΤΕΛΕΣΗ
# ============================================================
def extract_ast_features(code: str) -> Dict[str, int]:
    features = {
        "input_count": 0, "print_count": 0, "function_count": 0,
        "has_function": 0, "has_return": 0, "has_if": 0,
        "has_loop": 0, "has_for": 0, "has_while": 0,
        "has_list": 0, "has_dict": 0, "has_comprehension": 0,
        "has_modulo": 0, "has_append": 0, "has_len": 0,
        "has_range": 0, "has_try_except": 0, "has_import": 0,
        "code_length": len(code), "line_count": len([ln for ln in code.splitlines() if ln.strip()]),
    }
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return features

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            features["function_count"] += 1
            features["has_function"] = 1
        elif isinstance(node, ast.Return):
            features["has_return"] = 1
        elif isinstance(node, ast.If):
            features["has_if"] = 1
        elif isinstance(node, ast.For):
            features["has_loop"] = 1
            features["has_for"] = 1
        elif isinstance(node, ast.While):
            features["has_loop"] = 1
            features["has_while"] = 1
        elif isinstance(node, ast.List):
            features["has_list"] = 1
        elif isinstance(node, ast.Dict):
            features["has_dict"] = 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            features["has_comprehension"] = 1
            features["has_loop"] = 1
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            features["has_modulo"] = 1
        elif isinstance(node, ast.Try):
            features["has_try_except"] = 1
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            features["has_import"] = 1
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name == "input":
                    features["input_count"] += 1
                elif name == "print":
                    features["print_count"] += 1
                elif name == "len":
                    features["has_len"] = 1
                elif name == "range":
                    features["has_range"] = 1
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr == "append":
                    features["has_append"] = 1
    return features
def safe_exec_code(code: str, inputs: Optional[List[str]] = None, as_main: bool = False) -> Tuple[bool, Dict[str, Any], str, str]:
    if inputs is None:
        inputs = ["1", "2", "3", "4", "5", "10", "11", "15", "test"]

    env: Dict[str, Any] = {"__name__": "__main__" if as_main else "__student__"}
    stdout = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout):
            with patch("builtins.input", side_effect=inputs):
                exec(code, env, env)
        return True, env, stdout.getvalue(), ""
    except StopIteration:
        return False, env, stdout.getvalue(), "Ζητήθηκαν περισσότερες είσοδοι από όσες δόθηκαν στον έλεγχο."
    except Exception as e:
        return False, env, stdout.getvalue(), f"{type(e).__name__}: {e}"
# ============================================================
# ΑΥΤΟΜΑΤΗ ΠΡΟΤΑΣΗ ΥΛΙΚΟΥ
# ============================================================
def normalize_text(s: str) -> str:
    return str(s).lower().strip()
def discover_book_files() -> List[Dict[str, str]]:
    patterns = [
        "*.pdf", "*.docx",
        "resources/books/*.pdf", "resources/books/*.docx",
        "books/*.pdf", "books/*.docx",
    ]
    files: List[str] = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    files = sorted(set(files))

    resources = []
    for f in files:
        base = os.path.basename(f)
        if base.startswith("~$"):
            continue
        # Μην προτείνουμε την εκφώνηση ως βιβλίο.
        if re.match(r"week\s*\d+\.docx", base.lower()):
            continue
        title = os.path.splitext(base)[0]
        resources.append({
            "book_title": title,
            "book_file": f,
        })

    return resources
def load_video_resources(video_file: str = VIDEO_FILE) -> pd.DataFrame:
    if os.path.exists(video_file):
        try:
            df = pd.read_csv(video_file)
            for col in ["error_type", "title", "url", "keywords"]:
                if col not in df.columns:
                    df[col] = ""
            return df
        except Exception:
            pass

    return pd.DataFrame([
        {"error_type": "syntax", "title": DEFAULT_VIDEO_TITLE, "url": DEFAULT_VIDEO_URL, "keywords": "syntax python"},
        {"error_type": "algorithm", "title": DEFAULT_VIDEO_TITLE, "url": DEFAULT_VIDEO_URL, "keywords": "algorithm python"},
    ])
def select_video(category: str, videos_df: pd.DataFrame) -> Dict[str, str]:
    cat = normalize_text(category)
    if videos_df.empty:
        return {"video_title": DEFAULT_VIDEO_TITLE, "video_url": DEFAULT_VIDEO_URL}

    # 1) Exact match στο error_type.
    exact = videos_df[videos_df["error_type"].astype(str).str.lower().str.strip() == cat]
    if len(exact):
        r = exact.iloc[0]
        return {"video_title": str(r.get("title", DEFAULT_VIDEO_TITLE)), "video_url": str(r.get("url", DEFAULT_VIDEO_URL))}

    # 2) Match βάσει keywords.
    keys = RESOURCE_CATEGORY_KEYWORDS.get(cat, [cat])
    for _, r in videos_df.iterrows():
        haystack = f"{r.get('error_type','')} {r.get('title','')} {r.get('keywords','')}".lower()
        if any(k.lower() in haystack for k in keys):
            return {"video_title": str(r.get("title", DEFAULT_VIDEO_TITLE)), "video_url": str(r.get("url", DEFAULT_VIDEO_URL))}

    # 3) Fallback syntax.
    syntax_rows = videos_df[videos_df["error_type"].astype(str).str.lower().str.strip() == "syntax"]
    if len(syntax_rows):
        r = syntax_rows.iloc[0]
        return {"video_title": str(r.get("title", DEFAULT_VIDEO_TITLE)), "video_url": str(r.get("url", DEFAULT_VIDEO_URL))}

    r = videos_df.iloc[0]
    return {"video_title": str(r.get("title", DEFAULT_VIDEO_TITLE)), "video_url": str(r.get("url", DEFAULT_VIDEO_URL))}
def select_book(category: str, book_resources: List[Dict[str, str]]) -> Dict[str, str]:
    if not book_resources:
        return {"book_title": DEFAULT_BOOK_TITLE, "book_file": ""}

    cat = normalize_text(category)
    keys = RESOURCE_CATEGORY_KEYWORDS.get(cat, [cat])

    # 1) Προσπάθεια αντιστοίχισης με όνομα αρχείου.
    for b in book_resources:
        haystack = f"{b.get('book_title','')} {b.get('book_file','')}".lower()
        if any(k.lower() in haystack for k in keys):
            return {"book_title": b["book_title"], "book_file": b["book_file"]}

    # 2) Αν υπάρχει αρχείο Python/Pygame, το προτιμάμε ως γενικό βιβλίο Python.
    for b in book_resources:
        haystack = f"{b.get('book_title','')} {b.get('book_file','')}".lower()
        if "python" in haystack or "pygame" in haystack or "παιχν" in haystack:
            return {"book_title": b["book_title"], "book_file": b["book_file"]}

    return {"book_title": book_resources[0]["book_title"], "book_file": book_resources[0]["book_file"]}
def resource_is_needed(row: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Αποφασίζει αν πρέπει να προταθεί εκπαιδευτικό υλικό.

    Κρίσιμη αρχή:
    - Δεν προτείνουμε υλικό όταν ο κώδικας είναι ουσιαστικά σωστός.
    - Προτείνουμε υλικό μόνο όταν υπάρχει σαφές μαθησιακό έλλειμμα:
      syntax error, runtime error, πολύ χαμηλό function/main/algorithm score.
    """
    if not needs_pedagogical_feedback(row):
        return False, "Ο κώδικας είναι ουσιαστικά σωστός. Δεν απαιτείται ανατροφοδότηση ή υλικό."

    if row.get("syntax_error", False):
        return True, "Υπάρχει συντακτικό λάθος."

    if row.get("runtime_error", False):
        return True, "Υπάρχει runtime error."

    algorithm_score = float(row.get("algorithm_score", 100) or 0)
    function_score = float(row.get("function_score", 100) or 0)
    main_score = float(row.get("main_score", 100) or 0)

    # Αν η λύση είναι ουσιαστικά σωστή, δεν χρειάζεται υλικό.
    # Μικρές αποκλίσεις μορφής μένουν στο feedback, όχι ως recommendation material.
    if algorithm_score >= 85 and function_score >= 85:
        return False, "Ο κώδικας είναι ουσιαστικά σωστός. Δεν απαιτείται πρόσθετο υλικό."

    # Αν η συνάρτηση/αλγόριθμος είναι προβληματικά, χρειάζεται υλικό.
    if function_score < 80:
        return True, "Η βασική συνάρτηση/αλγοριθμική λογική δεν περνά αρκετά tests."

    if algorithm_score < 70:
        return True, "Το συνολικό algorithm score είναι χαμηλό."

    # Αν μόνο το main/input-output είναι αδύναμο, προτείνουμε υλικό μόνο όταν είναι σοβαρό.
    if main_score < 50:
        return True, "Το κύριο πρόγραμμα έχει σοβαρή αδυναμία σε input/output."

    return False, "Υπάρχουν μόνο μικρές παρατηρήσεις. Δεν απαιτείται υλικό."
def primary_learning_issue(row: Dict[str, Any]) -> Tuple[str, str, bool]:
    """
    Επιστρέφει (category, reason, needs_material).

    Αν needs_material=False, οι στήλες βιβλίου/βίντεο θα μείνουν κενές.
    """
    needed, reason_needed = resource_is_needed(row)
    if not needed:
        return "no_resource_needed", reason_needed, False

    if row.get("syntax_error", False):
        category = row.get("syntax_error_category") or "syntax"
        reason = row.get("syntax_explanation") or "Εντοπίστηκε συντακτικό λάθος."
        return str(category), str(reason), True

    if row.get("runtime_error", False):
        return "runtime_error", "Ο κώδικας εκτελείται με runtime error.", True

    if row.get("function_found", True) is False:
        return "function_missing", "Δεν εντοπίστηκε λειτουργική συνάρτηση για το ζητούμενο.", True

    # Δεν προτείνουμε υλικό μόνο επειδή το όνομα συνάρτησης δεν είναι ακριβές,
    # αν η συμπεριφορά είναι σωστή. Αν όμως φτάσαμε εδώ, υπάρχει ήδη σοβαρότερο θέμα.
    if row.get("has_return", 1) == 0 and float(row.get("function_score", 100) or 0) < 80:
        return "return_missing", "Η συνάρτηση δεν επιστρέφει σωστά αποτέλεσμα ή λείπει return.", True

    if float(row.get("function_score", 100) or 0) < 80:
        return "logic_even_filter", "Η συνάρτηση δεν επιστρέφει σταθερά τη σωστή λίστα άρτιων αριθμών.", True

    if float(row.get("main_score", 100) or 0) < 50:
        return "input_output", "Το κύριο πρόγραμμα έχει σοβαρή αδυναμία σε είσοδο/έξοδο δεδομένων.", True

    if row.get("has_list", 1) == 0 and row.get("exercise_type", "") == "evenlist":
        return "list_handling", "Η άσκηση απαιτεί χειρισμό λίστας.", True

    return "algorithm", "Χρειάζεται ενίσχυση αλγοριθμικής λογικής.", True
def attach_resources(results: pd.DataFrame) -> pd.DataFrame:
    videos_df = load_video_resources()
    books = discover_book_files()

    rows = []
    for _, r in results.iterrows():
        d = r.to_dict()
        category, reason, needs_material = primary_learning_issue(d)

        d["learning_issue_category"] = category
        d["learning_issue_reason"] = reason
        d["needs_learning_material"] = bool(needs_material)

        if needs_material:
            video = select_video(category, videos_df)
            book = select_book(category, books)
            d["recommended_book_title"] = book["book_title"]
            d["recommended_book_file"] = book["book_file"]
            d["recommended_video_title"] = video["video_title"]
            d["recommended_video_url"] = video["video_url"]
        else:
            d["recommended_book_title"] = ""
            d["recommended_book_file"] = ""
            d["recommended_video_title"] = ""
            d["recommended_video_url"] = ""

        rows.append(d)

    return pd.DataFrame(rows)
# ============================================================
# ΑΞΙΟΛΟΓΗΣΗ WEEK 6: evenlist
# ============================================================
def generate_evenlist_tests() -> List[List[int]]:
    tests = [
        [], [4, 5, 10, 11, 15], [1, 3, 5, 7],
        [2, 4, 6, 8], [0, -2, -3, 9, 12], [100, 101, 102],
    ]
    for _ in range(4):
        arr = [random.randint(-20, 30) for _ in range(random.randint(3, 8))]
        tests.append(arr)
    return tests
def expected_evens(values: List[int]) -> List[int]:
    return [x for x in values if isinstance(x, int) and x % 2 == 0]
def find_candidate_function(env: Dict[str, Any]) -> Tuple[Optional[str], Optional[Callable[..., Any]], bool]:
    if callable(env.get("evenlist")):
        return "evenlist", env["evenlist"], True

    candidates = []
    for name, obj in env.items():
        if callable(obj) and not name.startswith("__"):
            candidates.append((name, obj))

    for name, fn in candidates:
        try:
            sample = [1, 2, 3, 4]
            res = fn(sample.copy())
            if res == [2, 4]:
                return name, fn, False
        except Exception:
            continue
    return None, None, False
def evaluate_evenlist(code: str) -> Dict[str, Any]:
    feedback: List[str] = []
    strengths: List[str] = []
    weaknesses: List[str] = []

    syntax_details = check_syntax_detailed(code)
    features = extract_ast_features(code)

    if syntax_details["syntax_error"]:
        return {
            **syntax_details,
            "runtime_error": False,
            "function_found": False,
            "function_name_used": "",
            "exact_required_name": False,
            "function_score": 0.0,
            "main_score": 0.0,
            "structure_score": 0.0,
            "algorithm_score": 0.0,
            "correctness_label": "syntax_error",
            "feedback": syntax_details["syntax_explanation"],
            "strengths": "",
            "weaknesses": "Ο κώδικας δεν αναλύεται λόγω συντακτικού λάθους.",
            **features,
        }

    ok_module, env, out_module, err_module = safe_exec_code(code, inputs=["4 5 10 11 15", "4,5,10,11,15"], as_main=False)
    runtime_error = not ok_module

    if not ok_module:
        weaknesses.append(f"Πρόβλημα κατά την αρχική εκτέλεση/import: {err_module}")

    fn_name, fn, exact_name = find_candidate_function(env)
    function_found = fn is not None

    total_tests = 0
    passed_tests = 0
    failed_examples: List[str] = []

    if fn is not None:
        tests = generate_evenlist_tests()
        for arr in tests:
            total_tests += 1
            try:
                result = fn(arr.copy())
                expected = expected_evens(arr)
                if result == expected:
                    passed_tests += 1
                else:
                    failed_examples.append(f"input={arr}, expected={expected}, got={result}")
            except Exception as e:
                failed_examples.append(f"input={arr}, error={type(e).__name__}: {e}")
        function_score = passed_tests / total_tests if total_tests else 0.0
    else:
        function_score = 0.0

    main_passes = 0
    main_tests = [
        ("4 5 10 11 15", [4, 10]),
        ("4,5,10,11,15", [4, 10]),
        ("1 3 5", []),
        ("2 4 6", [2, 4, 6]),
    ]
    main_errors: List[str] = []
    for inp, expected in main_tests:
        ok, _env2, out, err = safe_exec_code(code, inputs=[inp], as_main=True)
        if ok:
            norm = out.replace(" ", "")
            expected_tokens_present = all(str(x) in norm for x in expected)
            if expected == []:
                expected_tokens_present = ("[]" in norm) or all(str(x) not in norm for x in [2, 4, 6, 8, 10])
            if expected_tokens_present:
                main_passes += 1
        else:
            main_errors.append(f"input='{inp}' -> {err}")
    main_score = main_passes / len(main_tests)

    structure_score = 0.0
    if features["has_function"]:
        structure_score += 0.25
    if features["has_return"]:
        structure_score += 0.25
    if features["has_loop"] or features["has_comprehension"]:
        structure_score += 0.20
    if features["has_modulo"]:
        structure_score += 0.20
    if features["has_list"] or features["has_append"] or features["has_comprehension"]:
        structure_score += 0.10

    algorithm_score = round(100 * (0.65 * function_score + 0.20 * main_score + 0.15 * structure_score), 2)

    if function_found and function_score == 1.0:
        strengths.append("Η βασική συνάρτηση επιστρέφει σωστά τους άρτιους αριθμούς σε δυναμικά tests.")
    elif function_found and function_score >= 0.70:
        strengths.append("Η βασική συνάρτηση λειτουργεί σε αρκετές περιπτώσεις, αλλά όχι σε όλες.")
    elif function_found:
        weaknesses.append("Η συνάρτηση υπάρχει, αλλά αποτυγχάνει σε αρκετά συμπεριφορικά tests.")
    else:
        weaknesses.append("Δεν εντοπίστηκε λειτουργική συνάρτηση που να επιστρέφει σωστά τους άρτιους αριθμούς.")

    if function_found and not exact_name:
        weaknesses.append(f"Η συνάρτηση φαίνεται σωστή, αλλά δεν έχει το ζητούμενο όνομα evenlist(). Βρέθηκε πιθανή συνάρτηση: {fn_name}().")
    elif exact_name:
        strengths.append("Χρησιμοποιήθηκε το ζητούμενο όνομα συνάρτησης evenlist().")

    if main_score >= 0.75:
        strengths.append("Το κύριο πρόγραμμα χειρίζεται ικανοποιητικά την εισαγωγή και εμφάνιση αποτελέσματος.")
    elif main_score > 0:
        weaknesses.append("Το κύριο πρόγραμμα δουλεύει μόνο σε ορισμένες μορφές εισόδου. Θέλει πιο ανθεκτικό χειρισμό input.")
    else:
        weaknesses.append("Το κύριο πρόγραμμα δεν εκτελείται σωστά στις δοκιμές εισόδου, ή δεν εμφανίζει καθαρά το αποτέλεσμα.")

    if features["has_modulo"]:
        strengths.append("Χρησιμοποιείται ο τελεστής modulo %, που είναι κατάλληλος για έλεγχο αρτιότητας.")
    else:
        weaknesses.append("Δεν εντοπίστηκε χρήση modulo %, άρα ο έλεγχος αρτιότητας ίσως γίνεται λανθασμένα ή μη σαφώς.")

    if features["has_return"] == 0:
        weaknesses.append("Η εκφώνηση ζητά συνάρτηση που επιστρέφει νέα λίστα· δεν εντοπίστηκε return.")

    if failed_examples:
        weaknesses.append("Παραδείγματα αποτυχίας: " + " ; ".join(failed_examples[:3]))

    if main_errors and main_score < 1.0:
        weaknesses.append("Ενδεικτικά runtime/main προβλήματα: " + " ; ".join(main_errors[:2]))

    if algorithm_score >= 85:
        label = "strong_correct"
        feedback.append("Πολύ καλή λύση: η συμπεριφορά του κώδικα είναι ουσιαστικά σωστή.")
    elif algorithm_score >= 65:
        label = "partially_correct"
        feedback.append("Μερικώς σωστή λύση: υπάρχει βασική κατανόηση, αλλά χρειάζονται διορθώσεις.")
    elif algorithm_score >= 35:
        label = "weak_attempt"
        feedback.append("Αδύναμη προσπάθεια: υπάρχουν σημαντικά προβλήματα στη συνάρτηση ή στο κύριο πρόγραμμα.")
    else:
        label = "incorrect"
        feedback.append("Η λύση δεν καλύπτει επαρκώς το ζητούμενο της άσκησης.")

    return {
        **syntax_details,
        "runtime_error": runtime_error and function_score == 0,
        "function_found": function_found,
        "function_name_used": fn_name or "",
        "exact_required_name": exact_name,
        "function_score": round(function_score * 100, 2),
        "main_score": round(main_score * 100, 2),
        "structure_score": round(structure_score * 100, 2),
        "algorithm_score": algorithm_score,
        "correctness_label": label,
        "feedback": " ".join(feedback),
        "strengths": " | ".join(strengths),
        "weaknesses": " | ".join(weaknesses),
        **features,
    }
# ============================================================
# ΓΕΝΙΚΗ ΑΞΙΟΛΟΓΗΣΗ ΑΝ ΔΕΝ ΑΝΑΓΝΩΡΙΣΤΕΙ ΑΣΚΗΣΗ
# ============================================================
def evaluate_generic(code: str, requirements: Dict[str, int]) -> Dict[str, Any]:
    syntax_details = check_syntax_detailed(code)
    features = extract_ast_features(code)

    if syntax_details["syntax_error"]:
        return {
            **syntax_details,
            "runtime_error": False,
            "algorithm_score": 0.0,
            "function_score": 0.0,
            "main_score": 0.0,
            "structure_score": 0.0,
            "correctness_label": "syntax_error",
            "feedback": syntax_details["syntax_explanation"],
            "strengths": "",
            "weaknesses": "Ο κώδικας δεν μπορεί να αξιολογηθεί λόγω συντακτικού λάθους.",
            **features,
        }

    ok, _env, out, err = safe_exec_code(code, as_main=True)
    score = 50.0 if ok else 20.0
    weaknesses = []
    strengths = []

    if ok:
        strengths.append("Ο κώδικας εκτελείται χωρίς runtime error στον γενικό έλεγχο.")
    else:
        weaknesses.append(f"Runtime error στον γενικό έλεγχο: {err}")

    for req, feat, msg in [
        ("requires_input", "input_count", "Η εκφώνηση φαίνεται να ζητά input, αλλά δεν βρέθηκε."),
        ("requires_print", "print_count", "Η εκφώνηση φαίνεται να ζητά print, αλλά δεν βρέθηκε."),
        ("requires_function", "has_function", "Η εκφώνηση φαίνεται να ζητά συνάρτηση, αλλά δεν βρέθηκε."),
        ("requires_list", "has_list", "Η εκφώνηση φαίνεται να ζητά λίστα, αλλά δεν εντοπίστηκε."),
        ("requires_dict", "has_dict", "Η εκφώνηση φαίνεται να ζητά λεξικό, αλλά δεν εντοπίστηκε."),
        ("requires_if", "has_if", "Η εκφώνηση φαίνεται να ζητά συνθήκη if, αλλά δεν βρέθηκε."),
        ("requires_loop", "has_loop", "Η εκφώνηση φαίνεται να ζητά επανάληψη, αλλά δεν βρέθηκε."),
    ]:
        if requirements.get(req, 0):
            value = features[feat]
            if value:
                score += 5
            else:
                score -= 5
                weaknesses.append(msg)

    score = max(0.0, min(100.0, score))
    label = "generic_pass" if score >= 70 else "generic_needs_review"
    return {
        **syntax_details,
        "runtime_error": not ok,
        "function_score": 0.0,
        "main_score": 0.0,
        "structure_score": 0.0,
        "algorithm_score": round(score, 2),
        "correctness_label": label,
        "feedback": "Γενική αξιολόγηση επειδή δεν αναγνωρίστηκε ειδικός τύπος άσκησης.",
        "strengths": " | ".join(strengths),
        "weaknesses": " | ".join(weaknesses),
        **features,
    }
# ============================================================
# ΠΡΟΦΙΛ, RECOMMENDATION, CLUSTERING
# ============================================================
def learning_profile(row: pd.Series) -> str:
    if row.get("syntax_error", False):
        return "Προφίλ Α: Συντακτικά κενά"
    if row.get("algorithm_score", 0) >= 85:
        return "Προφίλ Β: Ισχυρή αλγοριθμική κατανόηση"
    if row.get("function_score", 0) >= 80 and row.get("main_score", 0) < 60:
        return "Προφίλ Γ: Καλή συνάρτηση, αδύναμο κύριο πρόγραμμα/input-output"
    if row.get("function_score", 0) < 60 and row.get("has_modulo", 0) == 1:
        return "Προφίλ Δ: Γνωρίζει εργαλεία, αλλά έχει λογικά σφάλματα"
    if row.get("runtime_error", False):
        return "Προφίλ Ε: Runtime/debugging αδυναμίες"
    return "Προφίλ Ζ: Χρειάζεται ενίσχυση βασικής λογικής"
def recommendation(row: pd.Series) -> str:
    rec = []
    if row.get("syntax_error", False):
        rec.append("Επανάληψη βασικής σύνταξης Python και indentation.")
    if row.get("function_found", True) is False:
        rec.append("Άσκηση στη δημιουργία συναρτήσεων με σωστή παράμετρο και return.")
    if row.get("function_score", 100) < 80:
        rec.append("Εξάσκηση σε συμπεριφορικό έλεγχο συνάρτησης με διαφορετικές λίστες εισόδου.")
    if row.get("main_score", 100) < 70:
        rec.append("Εξάσκηση στη μετατροπή input string σε λίστα ακεραίων και καθαρή εμφάνιση αποτελέσματος.")
    if row.get("has_modulo", 1) == 0:
        rec.append("Επανάληψη τελεστή modulo % για έλεγχο άρτιων/περιττών αριθμών.")
    if row.get("has_return", 1) == 0:
        rec.append("Επανάληψη στη διαφορά print και return μέσα σε συνάρτηση.")
    if not rec:
        rec.append("Προτείνεται πιο σύνθετη άσκηση με φίλτρα λιστών και πολλαπλές συνθήκες.")
    return " | ".join(rec)
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
# ============================================================
# ΔΩΡΕΑΝ ΠΑΙΔΑΓΩΓΙΚΟΣ AI AGENT (ΠΡΟΑΙΡΕΤΙΚΟΣ)
# ============================================================
# class TestSyntaxError:
# class ProposedFeedbackError:
# class ProposedExerciseError:        
def attach_free_agent_feedback(
    results: pd.DataFrame,
    exercise_text: str,
    enabled: bool,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """
    Προσθέτει νέες AI στήλες. Δεν πειράζει καμία υπάρχουσα στήλη evaluator.
    """
    output = results.copy()

    if not enabled:
        for column, default in {
            "agent_verified_issue": "",
            "agent_scaffolding_guidance": "",
            "agent_student_level": "",
            "agent_next_step_challenge": "",
            "agent_recommended_resources_json": "[]",
            "agent_status": "disabled",
            "agent_evaluator_consistency": True,
        }.items():
            output[column] = default
        return output

    #agent = FreePedagogicalAgent()
    agent = BeginnerScaffoldingAgent();
    #agent2 = CodeOptimizationAgent();
    #agnet3 = SocraticDebuggingAgent();
    feedback_rows: List[Dict[str, Any]] = []

    for position, (_, row) in enumerate(output.iterrows()):
        row_dict = row.to_dict()

        # Σωστή λύση: δεν καλείται καν ο agent και δεν δίνεται ανατροφοδότηση.
        if not needs_pedagogical_feedback(row_dict):
            feedback = empty_pedagogical_feedback()
        elif limit is not None and position >= limit:
            feedback = fallback_pedagogical_feedback(row_dict)
            feedback["agent_status"] = "not_run_due_to_limit"
        else:
            feedback = agent.evaluate(
                exercise_text=exercise_text,
                row=row_dict,
            )

        feedback_rows.append(feedback)

    feedback_df = pd.DataFrame(feedback_rows, index=output.index)

    for column in feedback_df.columns:
        output[column] = feedback_df[column]

    return output
def suppress_feedback_for_correct_solutions(results: pd.DataFrame) -> pd.DataFrame:
    """
    Καθαρίζει κάθε περιγραφική ή διορθωτική ανατροφοδότηση από σωστές λύσεις.
    Οι αντικειμενικές βαθμολογίες και τα strengths παραμένουν διαθέσιμα.
    """
    output = results.copy()

    columns_to_clear = [
        "feedback",
        "weaknesses",
        "recommendation",
        "learning_issue_category",
        "learning_issue_reason",
        "recommended_book_title",
        "recommended_book_file",
        "recommended_video_title",
        "recommended_video_url",
    ]

    for index, row in output.iterrows():
        if needs_pedagogical_feedback(row.to_dict()):
            continue

        for column in columns_to_clear:
            if column in output.columns:
                output.at[index, column] = ""

        if "needs_learning_material" in output.columns:
            output.at[index, "needs_learning_material"] = False

    return output
# ============================================================
# MAIN - sk-ROur0EUGsKTqCaeHmD9TLpZmnudNeUtg0Z9HiPDsSYOQ7d0xKsrqzpYKGUdaWD70
# ============================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluator με προαιρετικό δωρεάν τοπικό AI agent."
    )
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Εκτέλεση μόνο deterministic evaluator.",
    )
    parser.add_argument(
        "--agent-limit",
        type=int,
        default=None,
        help="Τρέχει τον agent μόνο στις πρώτες N υποβολές.",
    )
    args = parser.parse_args()

    word_path = find_file(DEFAULT_WORD_FILE, "week*.docx")

    exercise_text = read_docx_text(word_path)
    week = detect_week_from_filename_or_text(word_path, exercise_text)
    exercise_type = detect_exercise_type(exercise_text)
    requirements = infer_requirements(exercise_text)

    if week is None:
        raise ValueError(
            "Δεν βρέθηκε εβδομάδα από το όνομα ή το κείμενο του Word. "
            "Χρησιμοποίησε όνομα π.χ. week6.docx"
        )

    excel_path, excel_diagnostics = find_excel_file_for_week(week)
    submissions, mapping = load_submissions(excel_path)

    available_weeks = sorted(
        submissions["week"].dropna().astype(int).unique().tolist()
    )
    week_df = submissions[
        submissions["week"] == week
    ].copy().reset_index(drop=True)

    if week_df.empty:
        raise ValueError(
            f"Δεν βρέθηκαν υποβολές στο Excel για week={week}. "
            f"Στο αρχείο {excel_path} υπάρχουν οι εβδομάδες: "
            f"{available_weeks}."
        )

    rows = []

    for _, r in week_df.iterrows():
        code = str(r["code"])

        if exercise_type == "evenlist":
            analysis = evaluate_evenlist(code)
        else:
            analysis = evaluate_generic(code, requirements)

        grade_num = r.get("grade_numeric", None)
        grader_disagreement = False

        if grade_num is not None:
            if grade_num >= 9 and analysis.get("algorithm_score", 0) < 70:
                grader_disagreement = True
            if grade_num < 5 and analysis.get("algorithm_score", 0) >= 85:
                grader_disagreement = True

        out = {
            "student_id": r.get("student_id", ""),
            "email": r.get("email", ""),
            "group": r.get("group", ""),
            "week": r.get("week", ""),
            "grade": r.get("grade", ""),
            "grade_numeric": grade_num,
            "exercise_type": exercise_type,
            "grader_disagreement_flag": grader_disagreement,
        }

        out.update(analysis)
        out["syntax_error_int"] = int(
            bool(out.get("syntax_error", False))
        )
        out["runtime_error_int"] = int(
            bool(out.get("runtime_error", False))
        )
        rows.append(out)

    results = pd.DataFrame(rows)
    results["learning_profile"] = results.apply(
        learning_profile,
        axis=1,
    )
    results["recommendation"] = results.apply(
        recommendation,
        axis=1,
    )

    results = attach_resources(results)
    results = suppress_feedback_for_correct_solutions(results)

    # Ο agent προσθέτει μόνο παιδαγωγικές στήλες.
    # Δεν αλλάζει καμία διάγνωση ή βαθμολογία evaluator.
    results = attach_free_agent_feedback(
        results=results,
        exercise_text=exercise_text,
        enabled=not args.no_agent,
        limit=args.agent_limit,
    )
    results = suppress_feedback_for_correct_solutions(results)

    results = add_clustering(results)

    summary = pd.DataFrame([
        {"metric": "excel_file", "value": excel_path},
        {"metric": "word_file", "value": word_path},
        {"metric": "detected_week", "value": week},
        {"metric": "exercise_type", "value": exercise_type},
        {"metric": "submissions_evaluated", "value": len(results)},
        {
            "metric": "mean_algorithm_score",
            "value": round(results["algorithm_score"].mean(), 2),
        },
        {
            "metric": "syntax_errors",
            "value": int(results["syntax_error_int"].sum()),
        },
        {
            "metric": "runtime_errors",
            "value": int(results["runtime_error_int"].sum()),
        },
        {"metric": "agent_enabled", "value": not args.no_agent},
        {"metric": "agent_limit", "value": args.agent_limit},
        {"metric": "detected_columns", "value": str(mapping)},
        {
            "metric": "excel_selection_diagnostics",
            "value": excel_diagnostics,
        },
        {
            "metric": "available_weeks_in_excel",
            "value": str(available_weeks),
        },
    ])

    with pd.ExcelWriter(OUTPUT_FILE, engine="xlsxwriter") as writer:
        results.to_excel(
            writer,
            sheet_name="student_results",
            index=False,
        )
        summary.to_excel(
            writer,
            sheet_name="summary",
            index=False,
        )

    print("Ο έλεγχος ολοκληρώθηκε.")
    print(f"Word εκφώνησης: {word_path}")
    print(f"Excel υποβολών: {excel_path}")
    print(f"Εβδομάδα που αξιολογήθηκε: {week}")
    print(f"Τύπος άσκησης: {exercise_type}")
    print(f"Agent ενεργός: {not args.no_agent}")
    print(f"Αποτελέσματα: {OUTPUT_FILE}")
if __name__ == "__main__":
    main()