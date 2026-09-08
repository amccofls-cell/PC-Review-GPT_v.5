# -*- coding: utf-8 -*-
"""
Python 1차 규칙 검증 모듈 — 명세서 7장.

기계적으로 100% 확실한 것만 판정한다:
1. 기본정보 일치 (제품명/성분명/제조판매사/제형 — 정규화 후 정확 비교)
2. 숫자·단위 (정규식 토큰 추출 후 동일 단위의 숫자 불일치 즉시 수정필요)
3. 약가 차이율 (신청의약품 - 비교의약품 최저가) / 비교의약품 최저가 × 100
그 외 서술형 항목은 절대 자동 판정하지 않고 "🟠 Claude 확인 필요" 로 넘긴다.
"""
import re

STATUS_OK = "✅ 일치"
STATUS_FIX = "⚠ 수정필요"
STATUS_CLAUDE = "🟠 Claude 확인 필요"
STATUS_UNKNOWN = "❌ 확인불가"

BASIC_FIELDS = ("제품명", "성분명", "제조판매사", "제형")
DESCRIPTIVE_FIELDS = (
    "효능효과", "용법용량", "이상반응", "금기사항", "신중투여", "상호작용",
    "소아_고령자투여", "임부_수유부투여", "과량투여처치", "보관_취급주의사항",
    "사용상주의사항", "포장단위", "유효기간", "기타",
)

_UNIT_TOKEN = re.compile(r"(\d+(?:[,.]\d+)?)\s*([a-zA-Z가-힣%]+)")
_SKIP_UNITS = {"형", "상", "번"}  # '제1형' 등 노이즈 유닛


def _norm_compare(text):
    s = str(text or "").strip()
    s = re.sub(r"\(주\)|（주）|주식회사|㈜|\[주\]", "", s)
    s = re.sub(r"[^0-9a-zA-Z가-힣]", "", s).lower()
    return s


def check_basic_info(value_a, value_b):
    """
    기본정보 정규화 비교. (주) 등 법인 표기는 무시.
    반환: (status, reason)
    """
    if value_b is None or not str(value_b).strip():
        return STATUS_UNKNOWN, "원문(MFDS)에 해당 정보가 없어 비교할 수 없습니다."
    a, b = _norm_compare(value_a), _norm_compare(value_b)
    if a and a == b:
        return STATUS_OK, f"표기 일치 (MFDS 원문: {str(value_b).strip()[:60]})"
    if not a:
        return STATUS_UNKNOWN, "비교표에 값이 비어 있습니다."
    return STATUS_FIX, f"표기 불일치 — 비교표: 「{str(value_a).strip()[:60]}」 / 원문: 「{str(value_b).strip()[:60]}」"


def _normalize_num(num_raw):
    try:
        return float(str(num_raw).replace(",", ""))
    except ValueError:
        return None


# 한국어/영문 단위를 비교용 표준 단위로 통일한다.
UNIT_CANON = {
    "마이크로그램": "mcg", "μg": "mcg", "ug": "mcg", "mcg": "mcg",
    "밀리그램": "mg", "mg": "mg", "그램": "g", "g": "g",
    "밀리리터": "ml", "ml": "ml", "l": "l", "iu": "iu", "단위": "unit",
    "%": "%", "정": "정", "캡슐": "캡슐", "회": "회", "일": "일",
    "시간": "시간", "분": "분", "초": "초", "주": "주", "개월": "개월", "세": "세",
}

# 숫자 + 단위뿐 아니라 1일 2회, 30분, 18세, 4시간 같은 임상 핵심 숫자를 잡는다.
_UNIT_TOKEN = re.compile(
    r"(?<![A-Za-z가-힣0-9])([0-9]+(?:[,.][0-9]+)?)\s*"
    r"(마이크로그램|μg|ug|mcg|밀리그램|mg|그램|g|밀리리터|mL|ml|L|IU|iu|단위|정|캡슐|회|일|시간|분|초|주|개월|세|%)"
    r"(?![A-Za-z가-힣0-9])",
    re.I,
)
_SKIP_UNITS = {"형", "상", "번"}


def extract_number_units(text):
    tokens = []
    for m in _UNIT_TOKEN.finditer(str(text or "")):
        num = _normalize_num(m.group(1))
        raw_unit = m.group(2).lower()
        unit = UNIT_CANON.get(raw_unit, raw_unit)
        if num is None or unit in _SKIP_UNITS:
            continue
        tokens.append((num, unit))
    return tokens


def _unique_tokens(tokens):
    out = []
    for token in tokens:
        if token not in out:
            out.append(token)
    return out


def compare_number_units(value_a, value_b):
    """숫자/단위의 '존재 여부'를 비교하되, 원문 전체의 동일 단위 숫자 때문에 오탐하지 않도록 한다.

    - 비교표의 숫자+단위가 원문에 동일하게 존재하면 통과 후보
    - 동일 단위만 있고 값이 다르면 수정 후보
    - 비교표가 원문의 일부를 요약한 것은 허용(원문에 없는 숫자만 경고)
    - 최종 의미 판정은 Claude가 담당
    """
    if value_b is None or not str(value_b).strip():
        return None
    ta = _unique_tokens(extract_number_units(value_a))
    tb = _unique_tokens(extract_number_units(value_b))
    if not ta:
        return []
    issues = []
    for num_a, unit_a in ta:
        same_unit = [(n, u) for n, u in tb if u == unit_a]
        if not same_unit:
            issues.append(f"비교표의 '{_fmt(num_a, unit_a)}'에 해당하는 원문 숫자·단위가 없음")
            continue
        if all(n != num_a for n, _ in same_unit):
            # 동일 단위의 후보가 하나뿐이거나, 명확히 다른 숫자만 존재할 때만 자동 경고.
            vals = sorted({n for n, _ in same_unit})
            shown = ", ".join(_fmt(n, unit_a) for n in vals[:6])
            issues.append(f"단위 {unit_a}: 비교표 {_fmt(num_a, unit_a)} vs 원문 {shown}")
    return issues


def _fmt(num, unit):
    return f"{num:g}{unit}"


def check_numeric_field(value_a, value_b):
    if value_b is None or not str(value_b).strip():
        return STATUS_UNKNOWN, "원문(MFDS)이 없어 비교할 수 없습니다."
    issues = compare_number_units(value_a, value_b)
    if issues:
        return STATUS_FIX, "숫자·단위 불일치 후보: " + " / ".join(issues[:3])
    return STATUS_CLAUDE, "숫자·단위상 명확한 불일치는 확인되지 않음. 의미 비교는 Claude에서 검증하세요."

def parse_price(value):
    """비교표 약가 셀에서 숫자 금액 추출. 없으면 None."""
    if value is None:
        return None
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)", str(value).replace(",", ""))
    try:
        return float(m.group(1).replace(",", ""))
    except (AttributeError, ValueError):
        return None


def check_price(value_a, hira_price):
    """
    비교표 약가 vs HIRA 상한금액 비교.
    반환: (status, reason, diff_pct_or_None)
    """
    if hira_price is None:
        return STATUS_UNKNOWN, "HIRA 약가정보가 없어 비교할 수 없습니다.", None
    pa = parse_price(value_a)
    if pa is None:
        return STATUS_UNKNOWN, "비교표의 약가 셀에서 금액을 해석하지 못했습니다.", None
    diff = (pa - hira_price) / hira_price * 100 if hira_price else None
    if abs(diff) < 0.005:
        return STATUS_OK, f"약가 일치 (비교표 {pa:,.0f}원 = HIRA {hira_price:,.0f}원)", diff
    return STATUS_FIX, f"약가 불일치 — 비교표 {pa:,.0f}원 vs HIRA {hira_price:,.0f}원 (차이 {diff:+.1f}%)", diff


def price_diff_percent(applicant_price, comparator_min_price):
    """
    명세서 7장 약가 차이율:
    (신청의약품가격 - 비교의약품최저가) / 비교의약품최저가 × 100
    """
    if applicant_price is None or comparator_min_price in (None, 0):
        return None
    return (applicant_price - comparator_min_price) / comparator_min_price * 100


def evaluate_pair(pair, reference_text, hira_price=None):
    """
    공통 셀 1건에 대한 1차 규칙 검증.
    pair: 명세서 8장 스키마 dict
    reference_text: 해당 제품·항목의 MFDS 원문 텍스트 (없으면 None)
    hira_price: 해당 제품의 HIRA 상한금액 (약가 항목만 사용)
    반환: (status, reason)
    """
    field = pair.get("field", "")
    value = pair.get("value", "")
    if field in BASIC_FIELDS:
        return check_basic_info(value, reference_text)
    if field == "약가":
        status, reason, _ = check_price(value, hira_price)
        return status, reason
    if field in DESCRIPTIVE_FIELDS or field:
        return check_numeric_field(value, reference_text)
    return STATUS_CLAUDE, "의미 비교는 Claude 웹에서 검증하세요."
