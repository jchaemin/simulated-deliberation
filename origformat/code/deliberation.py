# Persona wrapper shared with the survey code. Trimmed to the symbols the
# original-format replication imports: MODEL, persona_system, NEUTRAL_SYSTEM.
MODEL = "openai/gpt-4.1-mini"

def persona_system(p):
    return (
        f"당신은 아래 프로필의 대한민국 시민입니다.\n"
        f"[프로필] {p['age']}세 {p['sex']} · {p['district']} 거주 · "
        f"학력 {p['education_level']} · 직업 {p['occupation']} · {p['family_type']}\n"
        f"[배경] {p['persona']} {p.get('professional_persona','')} {p.get('family_persona','')}\n\n"
        f"답변은 항상 지정된 JSON 형식으로만 작성하세요."
    )

# The bare-model system prompt is, verbatim, the last line of persona_system —
# so the two conditions differ by exactly the persona block.
NEUTRAL_SYSTEM = "답변은 항상 지정된 JSON 형식으로만 작성하세요."
