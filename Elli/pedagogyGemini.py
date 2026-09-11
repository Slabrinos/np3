import json
import os
import re
from typing import Any, Dict

from google import genai
from google.genai import types

from evaluator import (
    needs_pedagogical_feedback,
    empty_pedagogical_feedback,
    fallback_pedagogical_feedback,
)

GEMINI_API_KEY = ("AQ.Ab8RN6J1lFQ3DZSrUj5DcsjNFiS6AHO0Sz45LXVHqpNtMl77rQ")
GEMINI_MODEL = "gemini-3.6-flash"


class FreePedagogicalAgent:
    """
    Pedagogical AI agent μέσω Google Gemini.

    Κρίσιμος περιορισμός:
    - Δεν βαθμολογεί.
    - Δεν αλλάζει syntax/runtime/algorithm_score.
    - Παράγει μόνο παιδαγωγική ανατροφοδότηση.
    """

    def __init__(self) -> None:
        self.model_name = GEMINI_MODEL
        self.client = None
        self.agent = None
        self.available = False
        self.init_error = ""

        try:
            api_key = GEMINI_API_KEY

            if not api_key:
                raise RuntimeError(
                    "Λείπει το GEMINI_API_KEY environment variable."
                )

            self.client = genai.Client(api_key=api_key)
            self.agent = self.client
            self.available = True

        except Exception as exc:
            self.available = False
            self.init_error = f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """
        Εξάγει JSON object ακόμα και αν το Gemini επιστρέψει
        ```json ... ``` ή επιπλέον κείμενο.
        """

        cleaned = str(text).strip()

        # Αφαίρεση markdown code fences.
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

        # Πρώτη προσπάθεια: ολόκληρο το response.
        try:
            value = json.loads(cleaned)

            if isinstance(value, dict):
                return value

        except (json.JSONDecodeError, TypeError):
            pass

        # Δεύτερη προσπάθεια: αναζήτηση ισορροπημένου JSON object.
        for start, char in enumerate(cleaned):

            if char != "{":
                continue

            depth = 0
            in_string = False
            escaped = False

            for end in range(start, len(cleaned)):

                current = cleaned[end]

                if escaped:
                    escaped = False
                    continue

                if current == "\\":
                    escaped = True
                    continue

                if current == '"':
                    in_string = not in_string
                    continue

                if in_string:
                    continue

                if current == "{":
                    depth += 1

                elif current == "}":
                    depth -= 1

                    if depth == 0:
                        candidate = cleaned[start:end + 1]

                        try:
                            value = json.loads(candidate)

                            if isinstance(value, dict):
                                return value

                        except json.JSONDecodeError:
                            break

        raise ValueError(
            "Το Gemini δεν επέστρεψε έγκυρο JSON."
        )

    @staticmethod
    def _safe_student_level(
        value: Any,
        fallback: str = "beginner",
    ) -> str:
        """
        Περιορίζει το student_level στις επιτρεπόμενες τιμές.
        """

        value = str(value or "").strip().lower()

        if value in {
            "beginner",
            "intermediate",
            "advanced",
        }:
            return value

        return fallback

    def evaluate(
        self,
        exercise_text: str,
        row: Dict[str, Any],
        json_EvalColumns: str
        ) -> Dict[str, Any]:

        if not needs_pedagogical_feedback(row):
            return empty_pedagogical_feedback()

        fallback = fallback_pedagogical_feedback(row)

        if not self.available or self.client is None:
            fallback["agent_status"] = (
                f"agent_unavailable: {self.init_error}"
            )
            return fallback

        # ---------------------------------------------------------
        # VERIFIED DATA
        # Αυτά τα δεδομένα προέρχονται αποκλειστικά από evaluator.
        # ---------------------------------------------------------

        try:
            algorithm_score = float(
                row.get("algorithm_score", 0) or 0
            )
        except (TypeError, ValueError):
            algorithm_score = 0.0

        verified = {
            "syntax_error": bool(
                row.get("syntax_error", False)
            ),
            "syntax_error_type": str(
                row.get("syntax_error_type", "")
            ),
            "syntax_explanation": str(
                row.get("syntax_explanation", "")
            ),
            "runtime_error": bool(
                row.get("runtime_error", False)
            ),
            "algorithm_score": algorithm_score,
            "correctness_label": str(
                row.get("correctness_label", "")
            ),
            "strengths": str(
                row.get("strengths", "")
            ),
            "weaknesses": str(
                row.get("weaknesses", "")
            ),
            "learning_profile": str(
                row.get("learning_profile", "")
            ),
            "recommendation": str(
                row.get("recommendation", "")
            ),
        }

        # ---------------------------------------------------------
        # OBJECTIVE CONDITION
        # ---------------------------------------------------------

        no_error = (
            not verified["syntax_error"]
            and not verified["runtime_error"]
            and verified["algorithm_score"] >= 85
        )

        prompt = f"""
Είσαι παιδαγωγικός AI Tutor για Python.

Η παρακάτω αξιολόγηση είναι ΕΠΑΛΗΘΕΥΜΕΝΗ
από deterministic evaluator.

Δεν επιτρέπεται να αλλάξεις ή να αμφισβητήσεις:
- syntax_error
- runtime_error
- algorithm_score
- correctness_label

ΕΚΦΩΝΗΣΗ:
{exercise_text[:5000]}

ΕΠΑΛΗΘΕΥΜΕΝΑ ΑΠΟΤΕΛΕΣΜΑΤΑ:
{json.dumps(verified, ensure_ascii=False)}

Παρήγαγε ΜΟΝΟ έγκυρο JSON.

Το JSON πρέπει να έχει ακριβώς αυτή τη μορφή:

{{
  "verified_issue": "...",
  "scaffolding_guidance": "...",
  "student_level": "beginner",
  "next_step_challenge": "...",
  "recommended_resources": []
}}

        

Κανόνες:

1. Αν algorithm_score >= 85 και δεν υπάρχει
   syntax/runtime error, μην επινοήσεις λάθος.

2. Σε σωστή λύση:
   recommended_resources = []

3. Σε λάθος λύση:
   μην δώσεις έτοιμο διορθωμένο κώδικα.

4. Δώσε scaffolding με καθοδηγητική ερώτηση,
   όχι έτοιμη λύση.

5. Το student_level πρέπει να είναι μόνο:
   beginner, intermediate ή advanced.

6. Το next_step_challenge πρέπει να είναι
   κατάλληλο για το επίπεδο του φοιτητή.

7. Μην αλλάξεις ποτέ τα verified αποτελέσματα
   του evaluator.

8. Μην κάνεις web search.
   Οι εκπαιδευτικοί πόροι ελέγχονται ξεχωριστά
   από το πρόγραμμα.

9. Γράψε στα ελληνικά.

10. Επέστρεψε μόνο JSON, χωρίς markdown,
    χωρίς ```json και χωρίς επιπλέον κείμενο.
"""

        prompt+=verified["learning_profile"]+verified["recommendation"]+verified["strengths"]+verified["weaknesses"]+verified["syntax_explanation"]+verified["syntax_error_type"];
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "Είσαι αυστηρός παιδαγωγικός "
                        "Python tutor. Επιστρέφεις μόνο JSON."
                    ),
                    temperature=0,
                    max_output_tokens=30000,
                    response_mime_type="application/json",
                ),
            )

            raw_output = response.text or ""

            parsed = self._extract_json(raw_output)

            # -----------------------------------------------------
            # VALIDATE MODEL OUTPUT
            # -----------------------------------------------------

            resources = parsed.get(
                "recommended_resources",
                [],
            )

            if not isinstance(resources, list):
                resources = []

            # Σωστή λύση => ΠΟΤΕ resources.
            if no_error:
                resources = []

            student_level = self._safe_student_level(
                parsed.get("student_level"),
                fallback.get(
                    "agent_student_level",
                    "beginner",
                ),
            )

            result = {
                "agent_verified_issue": str(
                    parsed.get("verified_issue")
                    or fallback[
                        "agent_verified_issue"
                    ]
                ),

                "agent_scaffolding_guidance": str(
                    parsed.get("scaffolding_guidance")
                    or fallback[
                        "agent_scaffolding_guidance"
                    ]
                ),

                "agent_student_level": student_level,

                "agent_next_step_challenge": str(
                    parsed.get("next_step_challenge")
                    or fallback[
                        "agent_next_step_challenge"
                    ]
                ),

                "agent_recommended_resources_json": json.dumps(
                    resources,
                    ensure_ascii=False,
                ),

                "agent_status": "ok",

                "agent_evaluator_consistency": True,
            }

            # -----------------------------------------------------
            # ABSOLUTE PROTECTION FOR CORRECT SOLUTIONS
            # -----------------------------------------------------

            if no_error:
                result["agent_verified_issue"] = (
                    "Δεν εντοπίστηκε ουσιαστικό λάθος "
                    "από τον αντικειμενικό evaluator."
                )

                result["agent_recommended_resources_json"] = "[]"

            return result

        except Exception as exc:
            fallback["agent_status"] = (
                f"agent_error: "
                f"{type(exc).__name__}: {exc}"
            )

            fallback["agent_evaluator_consistency"] = True

            return fallback
        