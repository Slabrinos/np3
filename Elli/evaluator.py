from typing import Any, Dict

def needs_pedagogical_feedback(row: Dict[str, Any]) -> bool:
    """
    Επιστρέφει True μόνο όταν υπάρχει επιβεβαιωμένη ανάγκη ανατροφοδότησης.

    Σωστή λύση σημαίνει:
    - χωρίς syntax error,
    - χωρίς runtime error,
    - algorithm_score >= 85,
    - function_score >= 85 όταν υπάρχει σχετική βαθμολογία,
    - main_score >= 70 όταν υπάρχει σχετική βαθμολογία.
    """
    if bool(row.get("syntax_error", False)):
        return True

    if bool(row.get("runtime_error", False)):
        return True

    algorithm_score = float(row.get("algorithm_score", 0) or 0)
    function_score = row.get("function_score", None)
    main_score = row.get("main_score", None)

    if algorithm_score < 85:
        return True

    if function_score is not None and float(function_score or 0) < 85:
        return True

    if main_score is not None and float(main_score or 0) < 70:
        return True

    return False
def empty_pedagogical_feedback(status: str = "skipped_no_need") -> Dict[str, Any]:
    """Κενό αποτέλεσμα για φοιτητή που δεν χρειάζεται ανατροφοδότηση."""
    return {
        "agent_verified_issue": "",
        "agent_scaffolding_guidance": "",
        "agent_student_level": "",
        "agent_next_step_challenge": "",
        "agent_recommended_resources_json": "[]",
        "agent_status": status,
        "agent_evaluator_consistency": True,
    }
def fallback_pedagogical_feedback(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ασφαλές fallback. Δεν αλλάζει ποτέ τα αποτελέσματα του evaluator.
    Χρησιμοποιείται αν το τοπικό μοντέλο ή το web search αποτύχει.
    """
    if not needs_pedagogical_feedback(row):
        return empty_pedagogical_feedback()

    if row.get("syntax_error", False):
        issue = str(row.get("syntax_explanation") or "Εντοπίστηκε συντακτικό λάθος.")
        question = (
            "Ποιον κανόνα σύνταξης παραβιάζει η γραμμή "
            f"{row.get('syntax_error_line', '')};"
        )
        level = "beginner"
        challenge = "Διόρθωσε πρώτα μία μικρή εκδοχή του ίδιου συντακτικού λάθους."
    elif row.get("runtime_error", False):
        issue = str(row.get("weaknesses") or "Ο κώδικας εμφανίζει runtime error.")
        question = "Ποια είναι η τελευταία μεταβλητή ή συνάρτηση πριν από το runtime error;"
        level = "beginner"
        challenge = "Δοκίμασε τον κώδικα με μία πολύ μικρή είσοδο και κατέγραψε τις τιμές."
    else:
        score = float(row.get("algorithm_score", 0) or 0)
        issue = str(row.get("weaknesses") or row.get("feedback") or "")
        if score >= 85:
            level = "advanced"
            issue = "Δεν εντοπίστηκε ουσιαστικό λάθος από τον αντικειμενικό evaluator."
            question = "Ποιες οριακές περιπτώσεις θα πρόσθετες στα tests σου;"
            challenge = "Βελτιστοποίησε τη λύση και γράψε unit tests."
        elif score >= 65:
            level = "intermediate"
            question = "Σε ποια είσοδο αποτυγχάνει η λύση και ποια τιμή αλλάζει λανθασμένα;"
            challenge = "Λύσε μία παρόμοια άσκηση με μία επιπλέον οριακή περίπτωση."
        else:
            level = "beginner"
            question = "Ποια είναι τα βήματα του αλγορίθμου πριν γράψεις τον κώδικα;"
            challenge = "Λύσε μία μικρότερη εκδοχή της ίδιας άσκησης με καθοδήγηση."

    return {
        "agent_verified_issue": issue,
        "agent_scaffolding_guidance": question,
        "agent_student_level": level,
        "agent_next_step_challenge": challenge,
        "agent_recommended_resources_json": "[]",
        "agent_status": "fallback_rule_based",
        "agent_evaluator_consistency": True,
    }
