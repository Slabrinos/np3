import os
import re
import json
from typing import Dict, Any, List
from pedagogyGemini import FreePedagogicalAgent

# Standard initialization constants assumed by your environment

class BeginnerScaffoldingAgent(FreePedagogicalAgent):
    """
    1. Beginner Scaffolding Agent
    Focuses on low-level foundational concepts, breaking down Python syntax, 
    and providing heavy step-by-step scaffolding questions without spoiling solutions.
    """
    def __init__(self) -> None:
        super().__init__()
        # Enforce higher precision/lower creativity for foundational guidance
        self.system_instruction = (
            "Είσαι ένας υποστηρικτικός Python Tutor για αρχάριους φοιτητές. "
            "Εστιάζεις σε βασικές έννοιες συντακτικού, απλές δομές δεδομένων "
            "και παρέχεις αναλυτική, βήμα-προς-βήμα καθοδήγηση (scaffolding) "
            "χωρίς να δίνεις έτοιμες λύσεις. Επιστρέφεις ΜΟΝΟ JSON."
        )

    def evaluate(self, exercise_text: str, row: Dict[str, Any]) -> Dict[str, Any]:
        # Force beginner bias in row context before invoking base logic or custom processing
        json_EvalColumns = """{
    "verified_issue": "string",
    "scaffolding_guidance": "string",
}"""
        row_copy = dict(row)
        if not row_copy.get("learning_profile"):
            row_copy["learning_profile"] = "beginner_foundational"
        return super().evaluate(exercise_text, row_copy, json_EvalColumns)


class CodeOptimizationAgent(FreePedagogicalAgent):
    """
    2. Code Optimization & Best Practices Agent
    Tailored for intermediate/advanced students who write functional code but 
    need guidance on Pythonic idioms, algorithmic complexity, and clean code.
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
    def evaluate(self, exercise_text: str, row: Dict[str, Any]) -> Dict[str, Any]:
        # Force beginner bias in row context before invoking base logic or custom processing
        json_EvalColumns = """{
                    "student_level": "beginner",
                    "next_step_challenge": "..."
                    }"""
        row_copy = dict(row)
        if not row_copy.get("learning_profile"):
            row_copy["learning_profile"] = "beginner_foundational"
        return super().evaluate(exercise_text, row_copy, json_EvalColumns)


class SocraticDebuggingAgent(FreePedagogicalAgent):
    """
    3. Socratic Debugging Agent
    Focuses purely on guided questioning to lead students to discover their own 
    runtime or logic errors through targeted edge cases and trace reasoning.
    """
    def __init__(self) -> None:
        super().__init__()
        self.system_instruction = (
            "Είσαι ένας Σωκρατικός AI Tutor για Python. "
            "Όταν υπάρχει σφάλμα, θέτεις στοχευμένες ερωτήσεις για τα edge cases "
            "και την ροή εκτέλεσης (tracing), καθοδηγώντας τον φοιτητή να "
            "εντοπίσει μόνος του το σημείο αποτυχίας. Επιστρέφεις ΜΟΝΟ JSON."
        )
    def evaluate(self, exercise_text: str, row: Dict[str, Any]) -> Dict[str, Any]:
        # Force beginner bias in row context before invoking base logic or custom processing
        json_EvalColumns = """{
                    "recommended_resources": []
                            }"""
        row_copy = dict(row)
        if not row_copy.get("learning_profile"):
            row_copy["learning_profile"] = "beginner_foundational"
        return super().evaluate(exercise_text, row_copy, json_EvalColumns)
