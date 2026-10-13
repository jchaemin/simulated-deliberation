CHOICE_ASK = "다음 두 입장 중 당신의 생각에 더 가까운 것은 무엇입니까? 반드시 하나를 선택하세요.\n"
CHOICE_ASK_PRIVATE = "이것은 토론과 별개의 비공개 설문입니다. 다음 두 입장 중 당신의 생각에 더 가까운 것은? 반드시 하나를 선택하세요.\n"
CHOICE_JSON = 'JSON으로만, 위 두 입장 중 하나를 그대로 적으세요: {"choice": "..."}'
CHOICE_JSON_SHORT = 'JSON으로만: {"choice": "..."}'


def _context(topic, transcript=None, booklet=None):
    return (f"[쟁점] {topic}\n" + (f"[자료]\n{booklet}\n\n" if booklet else "")
            + (f"[지금까지의 토론]\n{transcript}\n\n" if transcript else ""))


def forced_choice(topic, first, second, transcript=None, booklet=None, private=False):
    ask, tail = (CHOICE_ASK_PRIVATE, CHOICE_JSON_SHORT) if private else (CHOICE_ASK, CHOICE_JSON)
    return _context(topic, transcript, booklet) + ask + f"· {first}\n· {second}\n" + tail


def three_way(topic, first, second, undecided, transcript=None, booklet=None):
    return (_context(topic, transcript, booklet) + "다음 세 입장 중 당신의 생각에 가장 가까운 것은 무엇입니까?\n"
            f"· {first}\n· {second}\n· {undecided}\nJSON으로만, 위 세 입장 중 하나를 그대로 적으세요: {{\"choice\": \"...\"}}")


def neutral_option(topic, first, second):
    return (f"[쟁점] {topic}\n다음 두 입장 중 당신의 생각에 더 가까운 것은 무엇입니까?\n"
            f"· {first}\n· {second}\n어느 쪽도 아니라면 \"중립\".\n"
            'JSON으로만, 위 두 입장 중 하나를 그대로 적거나 "중립": {"choice": "..."}')


def labeled_choice(topic, option_a, option_b):
    return (f"[쟁점] {topic}\n(A) {option_a}\n(B) {option_b}\n\n"
            "당신은 A와 B 중 어느 쪽을 선택하시겠습니까? 정말 어느 쪽도 아니면 '중립'.\n"
            'JSON으로만: {"choice": "A" 또는 "B" 또는 "중립"}')


def support_rating(topic, position):
    return (f"[쟁점] {topic}\n당신은 아래 입장을 얼마나 지지합니까?\n[입장] {position}\n"
            "0 = 지지하지 않음, 1 = 어느 정도 지지, 2 = 강하게 지지\n"
            'JSON으로만: {"support": 0 또는 1 또는 2}')


def forced_choice_us(topic, first, second):
    return (f"[Issue] {topic}\n"
            f"Which of the following two positions is closer to your view? You must choose one.\n"
            f"· {first}\n· {second}\n"
            'Answer in JSON only, copying one of the two positions verbatim: {"choice": "..."}')


SPEAK_JSON = ' 발언만 JSON으로: {"public": "..."}'


def speaking_turn(q, name, transcript=None, side_cue=None, booklet=None):
    return (f"[쟁점] {q['topic']}\n" + (f"[자료]\n{booklet}\n\n" if booklet else "")
            + f"[논점] {q['poleA']}  또는  {q['poleB']}\n"
            + (f"[당신의 입장] 당신은 '{side_cue}' 쪽을 지지합니다.\n" if side_cue else "")
            + (f"[지금까지의 토론]\n{transcript}\n" if transcript else "[지금까지의 토론] 아직 발언이 없습니다.\n")
            + f"\n당신은 {name}입니다. 위 논의를 이어서 2~4문장으로 자신의 생각을 말하세요." + SPEAK_JSON)


def argued_opening(q, name, position):
    return (f"[쟁점] {q['topic']}\n[논점] {q['poleA']}  또는  {q['poleB']}\n[당신의 입장] 당신은 '{position}' 쪽입니다.\n\n"
            f"당신은 {name}입니다. 위 입장을 지지하는 이유를 2~4문장으로 말하세요." + SPEAK_JSON)


def free_opening(q, name):
    return (f"[쟁점] {q['topic']}\n[논점] {q['poleA']}  또는  {q['poleB']}\n"
            f"\n당신은 {name}입니다. 두 입장 중 어느 쪽에 더 가까운지와 그 이유를 2~4문장으로 말하세요." + SPEAK_JSON)
