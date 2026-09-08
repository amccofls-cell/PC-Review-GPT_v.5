# -*- coding: utf-8 -*-
"""
Claude용 검증 프롬프트 자동 생성 모듈 — 명세서 9장 구조 그대로.

중요: 이 모듈은 텍스트를 생성해 클립보드에 복사해 주는 역할만 한다.
Claude API 를 호출하는 코드는 일절 포함하지 않는다.
"""
from modules import mfds_api

PROMPT_ROLE = """[역할]
너는 의약품 심의자료의 사실관계를 검증하는 검토자다."""

PROMPT_PRINCIPLE = """[검증 원칙]
- 아래 제공된 MFDS 허가사항 원문과 HIRA 약가정보, 그리고 심의자료 비교표만을 근거로 판단하라.
- 너의 일반적인 의약학 지식, 인터넷 지식, 기억하는 허가사항으로 보완하지 마라. 근거가 없으면 \"확인불가\"로 답하라.
- 문자열이 아니라 의미를 비교하라. 표현이 달라도 핵심 의미가 같으면 \"표현차이\"다.
- 대상환자·연령·이전치료 여부·병용치료·바이오마커·용량·투여횟수·투여기간·감량/중단 조건 등 핵심 조건이
  삭제되어 범위가 넓어지거나, 원문에 없는 내용이 추가되어 있으면 \"수정필요\"다."""

PROMPT_REQUEST = """[검증 요청]
각 항목별로 비교표 내용이 위 원문과 의미상 일치하는지 판단하라.
판정은 다음 5개 중 하나: 일치 / 수정필요 / 확인필요 / 표현차이 / 확인불가.
각 판정에는 반드시 원문 근거를 함께 제시하라."""

PROMPT_FORMAT = """[출력 형식]
| 제품 | 항목 | 판단 | 이유 | 원문 근거 |"""

_BASIC_INFO_KEYS = (
    "제품명", "영문제품명", "성분명", "주성분영문명", "전문일반구분", "ATC코드",
    "원료약품및분량(함량)", "제조판매사", "제형", "포장단위", "유효기간", "보관정보",
    "성상", "EDI코드", "바코드(표준코드)",
)

# 항목별 MFDS 원문 추출 키
NB_KEY_FOR_FIELD = {
    "이상반응": "이상반응",
    "금기사항": "금기사항",
    "신중투여": "신중투여",
    "상호작용": "상호작용",
    "소아_고령자투여": "소아_고령자투여",
    "임부_수유부투여": "임부_수유부투여",
    "과량투여처치": "과량투여처치",
    "보관_취급주의사항": "보관_취급주의사항",
}


def _display_label(product_record):
    return product_record.get("prompt_label") or product_record.get("label") or "(품목)"


def _product_block_header(product_record):
    return f"--- {_display_label(product_record)} ---"


def _role_value(product_record):
    return product_record.get("role") or product_record.get("group_label") or product_record.get("label") or ""


def _target_lines(products):
    applicant = [p for p in products if "신청" in _role_value(p)]
    comparators = [p for p in products if p not in applicant]
    if not applicant and products:
        applicant = [products[0]]
        comparators = products[1:]

    parts = ["[검증 대상 제품]"]
    applicant_labels = [_display_label(p) for p in applicant]
    parts.append("신청의약품: " + (", ".join(applicant_labels) if applicant_labels else "(신청의약품)"))

    comp_buckets = {}
    for p in comparators:
        role = _role_value(p)
        comp_buckets.setdefault(role or "비교의약품", []).append(_display_label(p))
    for role, labels in comp_buckets.items():
        parts.append(f"{role}: " + ", ".join(labels))
    return parts


def _table_pairs_text(pairs):
    lines = []
    for p in pairs:
        field = p.get("field", "")
        value = str(p.get("value", "")).strip()
        if value:
            lines.append(f"- {field}: {value}")
        else:
            lines.append(f"- {field}: (비어 있음)")
    return "\n".join(lines)


def _mfds_field_text(detail, field):
    """항목별 MFDS 원문 텍스트 추출 (요약하지 않음)."""
    if field in ("효능효과", "용법용량"):
        return str(detail.get(field) or "").strip()
    if field in NB_KEY_FOR_FIELD:
        nb = detail.get("사용상주의사항") or {}
        return str(nb.get(NB_KEY_FOR_FIELD[field]) or "").strip()
    if field == "기본정보":
        lines = []
        for k in _BASIC_INFO_KEYS:
            v = detail.get(k)
            if v:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
    return mfds_api.detail_to_raw_text(detail)


def _hira_text(hira_rows):
    if not hira_rows:
        return "(HIRA 약가정보 없음)"
    lines = []
    for r in hira_rows:
        lines.append(
            f"품목명: {r.get('itmNm')} / 제조사: {r.get('mnfEntpNm')} / "
            f"품목코드: {r.get('mdsCd')} / 상한금액: {r.get('mxCprc')}원 / "
            f"적용시작일: {r.get('adtStaDd') or '—'} / 판매종료일: {r.get('sellEptDd') or '—'} / "
            f"급여구분: {r.get('payTpNm')} / 약효분류: {r.get('meftDivNo')}"
        )
    return "\n".join(lines)


def build_full_prompt(products):
    """
    products: [{"label", "prompt_label", "role", "detail", "hira_rows", "pairs"}...]
    전체 자료(전 제품 × MFDS 원문 + HIRA + 비교표) 프롬프트를 생성한다.
    """
    parts = [PROMPT_ROLE, PROMPT_PRINCIPLE]
    parts.extend(_target_lines(products))

    parts.append("\n[MFDS 허가사항 원문]")
    for p in products:
        parts.append(_product_block_header(p))
        parts.append(mfds_api.detail_to_raw_text(p.get("detail") or {"error": "MFDS 조회 실패(데이터 없음)"}))

    parts.append("\n[HIRA 약가정보]")
    for p in products:
        parts.append(_product_block_header(p))
        parts.append(_hira_text(p.get("hira_rows")))

    parts.append("\n[심의자료 비교표]")
    for p in products:
        parts.append(_product_block_header(p))
        parts.append(_table_pairs_text(p.get("pairs", [])))

    parts.append("\n" + PROMPT_REQUEST)
    parts.append(PROMPT_FORMAT)
    return "\n".join(parts)


def build_product_prompt(product):
    """단일 제품용 프롬프트."""
    return build_full_prompt([product])


def build_field_prompt(field, products):
    """
    특정 항목(효능효과/용법용량/이상반응/금기사항/상호작용/기본정보 등)만 추린 프롬프트.
    MFDS 원문은 해당 항목 원문만, 비교표는 해당 항목 셀만 포함한다(요약 없음).
    """
    parts = [PROMPT_ROLE, PROMPT_PRINCIPLE]
    parts.extend(_target_lines(products))

    parts.append("\n[MFDS 허가사항 원문 (해당 항목)]")
    for p in products:
        parts.append(_product_block_header(p))
        txt = _mfds_field_text(p.get("detail") or {}, field)
        parts.append(txt if txt else "(원문에 해당 항목 없음)")

    parts.append("\n[HIRA 약가정보]")
    for p in products:
        parts.append(_product_block_header(p))
        parts.append(_hira_text(p.get("hira_rows")))

    parts.append("\n[심의자료 비교표 (해당 항목)]")
    for p in products:
        parts.append(_product_block_header(p))
        field_pairs = [pp for pp in p.get("pairs", []) if pp.get("field") == field]
        parts.append(_table_pairs_text(field_pairs) if field_pairs else "(해당 항목 셀 없음)")

    parts.append("\n" + PROMPT_REQUEST)
    parts.append(PROMPT_FORMAT)
    return "\n".join(parts)


def build_basic_info_prompt(products):
    """기본정보(제품명/성분명/제조판매사/제형 등)만 추린 프롬프트."""
    return build_field_prompt("기본정보", products)


def build_grouped_prompt(group_records):
    """비교표의 한 제품열을 동일 제품군(여러 함량) 단위로 검증하는 프롬프트.

    group_records 예:
      {"table_label": "Fentora buccal tab", "group_label": "비교의약품2",
       "match_method": "ordinal", "products": [...], "pairs": [...]}
    """
    parts = [PROMPT_ROLE]
    parts.append("""[핵심 검증 원칙]
- 비교표의 한 제품 열은 동일 제품의 여러 함량을 한 셀에 묶어 요약할 수 있다.
- 따라서 개별 함량 품목 하나와 비교표 전체 셀을 1:1 문자열 비교하지 말고, 해당 제품군에 포함된 모든 MFDS 원문을 함께 고려하라.
- 비교표가 원문을 간결하게 요약한 경우 핵심 의미가 보존되면 일치 또는 표현차이로 판단하라.
- 원문에 없는 조건/수치/대상군을 추가하거나, 임상적으로 중요한 제한조건을 삭제하여 의미가 넓어지면 수정필요다.
- 숫자·단위·횟수·간격·기간·연령·최대용량은 특히 엄격하게 확인하라.
- 제공된 원문에 없는 사실은 일반 지식으로 보완하지 말고 확인불가로 판단하라.""")
    parts.append("[검증 대상 제품군]")
    for g in group_records:
        parts.append(f"--- 비교표 제품열: {g.get('table_label','')} / 연결 그룹: {g.get('group_label','')} / 연결 방식: {g.get('match_method','')} ---")
        for p in g.get("products", []):
            label = p.get("prompt_label") or p.get("item_name") or p.get("label") or "품목"
            parts.append(f"[MFDS 품목] {label}")
            parts.append(mfds_api.detail_to_raw_text(p.get("detail") or {"error": "MFDS 조회 실패(데이터 없음)"}))
        parts.append("[HIRA 약가정보]")
        parts.append(_hira_text(g.get("hira_rows")))
        parts.append("[심의자료 비교표 해당 열]")
        parts.append(_table_pairs_text(g.get("pairs", [])))
    parts.append("""[검증 요청]
각 비교표 제품열의 각 항목을 연결된 제품군의 MFDS 원문과 비교하라.
특히 다음을 구분하라.
1. 일치: 핵심 의미와 조건이 원문과 일치
2. 표현차이: 표현만 다르고 의미가 동일
3. 수정필요: 중요한 조건·수치·범위가 달라짐, 원문에 없는 내용이 추가됨, 또는 중요한 조건이 누락됨
4. 확인필요: 자료만으로 명확한 판단이 어려움
5. 확인불가: 공식 원문에서 근거를 확인하지 못함

제품군 연결 방식이 '비교표 열 순서로 매칭(확인 권장)'인 경우 제품 식별도 함께 주의해서 확인하라.""")
    parts.append("[출력 형식]\n| 제품열 | 연결그룹 | 항목 | 판단 | 이유 | 원문 근거 |")
    return "\n".join(parts)
