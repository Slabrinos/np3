import os
import re
import json
from typing import Dict, Any, List
from pedagogyGemini import FreePedagogicalAgent

# Standard initialization constants assumed by your environment

class A1(FreePedagogicalAgent):
    """
    """
    def __init__(self) -> None:
        super().__init__()
        # Enforce higher precision/lower creativity for foundational guidance
        self.system_instruction = (
    "Είσαι Python Tutor για αρχάριους φοιτητές. "
    "Ο κώδικας που λαμβάνεις έχει αριθμημένες γραμμές. "
    "Όταν εντοπίζεις λάθος, ΠΡΕΠΕΙ να επιστρέφεις τον ακριβή αριθμό γραμμής "
    "όπως εμφανίζεται μπροστά από τη γραμμή κώδικα. "
    "Μην υπολογίζεις μόνος σου αριθμούς γραμμών. "
    "Αν υπάρχουν πολλά λάθη, επέστρεψε όλα τα line numbers. "
    "Για κάθε λάθος επέστρεψε line, error_type, explanation και hint. "
    "Δεν δίνεις ολόκληρη έτοιμη λύση. "
    "Επιστρέφεις ΜΟΝΟ έγκυρο JSON. "
    'Μορφή: {"errors":[{"line":10,"error_type":"ValueError",'
    '"explanation":"...","hint":"..."}]}'
)

    def evaluate(self, exercise_text: str, row: Dict[str, Any], json_EvalColumns: str = None) -> Dict[str, Any]:
        # Force beginner bias in row context before invoking base logic or custom processing
        
        row_copy = dict(row)
        if not row_copy.get("learning_profile"):
            row_copy["learning_profile"] = "beginner_foundational"
        return super().evaluate(exercise_text, row_copy, json_EvalColumns)


class A2(FreePedagogicalAgent):
    """
    """
    def __init__(self) -> None:
        super().__init__()
        self.system_instruction = (
            "Είσαι ένας Python Code Reviewer & Pedagogical Tutor. "
            "Εστιάζεις σε Pythonic πρακτικές, βελτιστοποίηση αλγορίθμων, "
            "καθαρότητα κώδικα (PEP8) και αποδοτικότητα. "
            "Προκαλείς τον φοιτητή να σκεφτεί πιο προηγμένες λύσεις. "
            "Επιστρέφεις ΜΟΝΟ JSON."
        )
    def evaluate(self, exercise_text: str, row: Dict[str, Any], json_EvalColumns: str = None) -> Dict[str, Any]:
        # Force beginner bias in row context before invoking base logic or custom processing
        json_EvalColumns = """{
                    "student_level": "beginner",
                    "next_step_challenge": "..."
                    }"""
        row_copy = dict(row)
        if not row_copy.get("learning_profile"):
            row_copy["learning_profile"] = "beginner_foundational"
        return super().evaluate(exercise_text, row_copy, json_EvalColumns)


class A3(FreePedagogicalAgent):
    """
    """
    def __init__(self) -> None:
        super().__init__()
        self.system_instruction = (
            "Είσαι ένας Σωκρατικός AI Tutor για Python. "
            "Όταν υπάρχει σφάλμα, θέτεις στοχευμένες ερωτήσεις για τα edge cases δίνοντας την αρίθμηση της γραμμης που βρίσκεται ο λάθος κώδικας"
            "και την ροή εκτέλεσης (tracing), καθοδηγώντας τον φοιτητή να "
            "εντοπίσει μόνος του το σημείο αποτυχίας. Επιστρέφεις ΜΟΝΟ JSON."
        )
    def evaluate(self, exercise_text: str, row: Dict[str, Any], json_EvalColumns: str = None) -> Dict[str, Any]:
        # Force beginner bias in row context before invoking base logic or custom processing
        json_EvalColumns = """{
                    "recommended_resources": []
                            }"""
        row_copy = dict(row)
        if not row_copy.get("learning_profile"):
            row_copy["learning_profile"] = "beginner_foundational"
        return super().evaluate(exercise_text, row_copy, json_EvalColumns)
