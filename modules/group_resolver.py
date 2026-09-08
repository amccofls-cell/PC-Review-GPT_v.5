# -*- coding: utf-8 -*-
"""비교표의 '제품 열'을 선택된 신청/비교약 그룹에 연결하는 보조 모듈.

비교표는 한 열에 동일 제품의 여러 함량을 묶어 적는 경우가 많다.
따라서 셀 하나를 개별 품목 1건에 억지로 연결하지 않고, 가능한 경우 그룹 단위로 연결한다.
"""
import re


def _norm(text):
    s = str(text or "").lower().strip()
    s = re.sub(r"[^0-9a-z가-힣]", "", s)
    return s


def _tokens(text):
    s = str(text or "").lower()
    return {x for x in re.findall(r"[a-z]{2,}|[가-힣]{2,}|\d+(?:\.\d+)?", s) if x}


def ordered_groups(products):
    """products의 최초 등장 순서를 유지한 그룹 목록."""
    out, seen = [], set()
    for p in products or []:
        gid = str(p.get("group_id") or "")
        if gid and gid not in seen:
            seen.add(gid)
            out.append(gid)
    return out


def group_label(products, gid):
    for p in products or []:
        if str(p.get("group_id") or "") == gid:
            return str(p.get("group_label") or gid)
    return gid


def resolve_column_group(label, products, used=None, allow_ordinal=True):
    """비교표 제품열 이름을 그룹에 연결한다.

    반환 dict: {group_id, confidence, method, label}
    confidence: exact / fuzzy / ordinal / none
    """
    used = set(used or [])
    groups = ordered_groups(products)
    nlabel = _norm(label)
    if not nlabel:
        return {"group_id": None, "confidence": "none", "method": "empty", "label": label}

    # 1) 그룹명/역할/제품명에 정확히 포함되는 경우
    exact = []
    for gid in groups:
        members = [p for p in products if str(p.get("group_id") or "") == gid]
        candidates = {group_label(products, gid)}
        for p in members:
            candidates.update([
                p.get("label", ""), p.get("item_name", ""),
                (p.get("detail") or {}).get("제품명", ""),
            ])
        if any(nlabel == _norm(c) or nlabel in _norm(c) or _norm(c) in nlabel for c in candidates if c):
            exact.append(gid)
    exact = [g for g in exact if g not in used] or exact
    if len(exact) == 1:
        return {"group_id": exact[0], "confidence": "exact", "method": "제품명/그룹명 일치", "label": label}

    # 2) 토큰 겹침으로 fuzzy 후보
    lt = _tokens(label)
    scored = []
    for gid in groups:
        if gid in used:
            continue
        members = [p for p in products if str(p.get("group_id") or "") == gid]
        text = " ".join([group_label(products, gid)] + [str(p.get("item_name") or "") for p in members])
        score = len(lt & _tokens(text))
        if score:
            scored.append((score, gid))
    if scored:
        scored.sort(reverse=True)
        if len(scored) == 1 or scored[0][0] > scored[1][0]:
            return {"group_id": scored[0][1], "confidence": "fuzzy", "method": "제품명 토큰 유사", "label": label}

    # 3) 제품열 개수와 그룹 개수가 같고 순서가 명확한 경우에만 순서 매칭.
    # 호출부에서 전체 열을 먼저 수집해 사용해야 하므로 여기서는 별도 함수가 제공된다.
    return {"group_id": None, "confidence": "none", "method": "매칭 실패", "label": label}


def resolve_columns(labels, products, role_by_label=None):
    """표에 등장한 고유 제품열을 그룹에 일대일 매칭한다."""
    unique = []
    for x in labels:
        x = str(x or "").strip()
        if x and x not in unique:
            unique.append(x)
    groups = ordered_groups(products)
    results = {}
    used = set()
    role_by_label = role_by_label or {}

    # 신청의약품 표기가 있는 열은 applicant 그룹에 우선 연결한다.
    applicant_ids = [g for g in groups if g == "applicant"]
    for label in unique:
        role = str(role_by_label.get(label) or "")
        if "신청" in role and applicant_ids:
            gid = "applicant"
            if gid not in used:
                results[label] = {"group_id": gid, "confidence": "exact", "method": "비교표의 신청의약품 표기", "label": label}
                used.add(gid)
    unresolved = []
    for label in unique:
        if label in results:
            continue
        r = resolve_column_group(label, products, used=used, allow_ordinal=False)
        if r["group_id"]:
            results[label] = r
            used.add(r["group_id"])
        else:
            unresolved.append(label)

    # 매우 흔한 실제 심의표 형태: 열 순서가 신청/비교1/비교2... 순으로 동일.
    # 자동 적용은 고유 열 수 == 그룹 수일 때만 허용하고, 결과에 method를 남긴다.
    if unresolved and len(unique) == len(groups) and len(results) < len(groups):
        remaining_groups = [g for g in groups if g not in used]
        remaining_labels = [x for x in unique if x not in results]
        # 신청 열이 명시적으로 매칭된 경우에만 나머지 비교약을 열 순서로 연결한다.
        # 신청 열조차 확인되지 않은 상태에서는 순서 추정을 하지 않는다.
        applicant_mapped = any(r.get("group_id") == "applicant" for r in results.values())
        if applicant_mapped:
            for label, gid in zip(remaining_labels, remaining_groups):
                results[label] = {
                    "group_id": gid,
                    "confidence": "ordinal",
                    "method": "신청 열 확인 후 비교표 열 순서로 매칭(확인 권장)",
                    "label": label,
                }
    return results
