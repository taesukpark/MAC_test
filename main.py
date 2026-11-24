

"""AI의 MAC(Multiply-Accumulate) 연산을 흉내내는 미니 계산기."""
import json
import os
import time
 
EPSILON = 1e-9          # 부동소수점 비교 허용 오차 (|A-B| < EPSILON 이면 동점)
DATA_PATH = r"C:\Users\lucidts1102\test3\data.json"
PERF_REPEAT = 100       # 성능 측정 반복 횟수
PERF_SIZES = (5, 13, 25)
 
 
# ───────────────────────── 데이터 구조 ─────────────────────────
class Matrix:
    """n×n 2차원 데이터 (패턴/필터 공용). 3×3, 5×5, 13×13, 25×25 등 임의의 n 지원."""
 
    def __init__(self, n, fill=0.0):
        self.n = n
        self._d = [[fill] * n for _ in range(n)]
 
    @classmethod
    def from_rows(cls, rows):
        n = len(rows)
        if n == 0 or any(len(r) != n for r in rows):
            raise ValueError("정사각형(n×n)이 아닙니다.")
        m = cls(n)
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                m.set(i, j, float(v))   # 숫자가 아니면 ValueError
        return m
 
    def set(self, r, c, value):
        self._d[r][c] = value
 
    def get(self, r, c):
        return self._d[r][c]
 
    def rows(self):
        return self._d
 
 
# ───────────────────────── 핵심 연산 ─────────────────────────
def mac(pattern, filt):
    """같은 위치끼리 곱해서 모두 더한다. 연산 횟수 = n² 번의 곱셈-누적."""
    p, f = pattern.rows(), filt.rows()
    total = 0.0
    for i in range(pattern.n):
        pi, fi = p[i], f[i]
        for j in range(pattern.n):
            total += pi[j] * fi[j]
    return total
 
 
def timed_mac(pattern, filt):
    t0 = time.perf_counter()
    score = mac(pattern, filt)
    return score, (time.perf_counter() - t0) * 1000.0
 
 
def judge(score_a, score_b, label_a, label_b, undecided):
    """비교 정책: |차이| < EPSILON 이면 판정불가, 아니면 큰 쪽."""
    if abs(score_a - score_b) < EPSILON:
        return undecided
    return label_a if score_a > score_b else label_b
 
 
# ───────────────────────── 메뉴 1: 사용자 입력 ─────────────────────────
def read_matrix(title, n):
    """n줄을 입력받는다. 형식 오류 시 안내문구 출력 후 처음부터 재입력."""
    while True:
        print(f"{title} ({n}x{n}) 를 입력하세요. 각 줄에 {n}개의 숫자를 공백으로 구분:")
        rows, ok = [], True
        for _ in range(n):
            parts = input().split()
            if len(parts) != n:
                print(f"입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요.")
                ok = False
                break
            try:
                rows.append([float(x) for x in parts])
            except ValueError:
                print("입력 형식 오류: 숫자만 입력할 수 있습니다. (숫자 파싱 실패)")
                ok = False
                break
        if ok:
            return Matrix.from_rows(rows)
 
 
def menu_user_input():
    raw = input("행렬 크기 n을 입력하세요 (기본 3, 엔터=3): ").strip()
    try:
        n = int(raw) if raw else 3
        if n < 1:
            raise ValueError
    except ValueError:
        print("입력 형식 오류: n은 1 이상의 정수여야 합니다. 기본값 3을 사용합니다.")
        n = 3
    fa = read_matrix("필터 A", n)
    fb = read_matrix("필터 B", n)
    pat = read_matrix("패턴", n)
 
    sa, ta = timed_mac(pat, fa)
    sb, tb = timed_mac(pat, fb)
    result = judge(sa, sb, "A", "B", "판정불가")
    print("\n[결과]")
    print(f"  필터 A MAC 점수: {sa:.4f}")
    print(f"  필터 B MAC 점수: {sb:.4f}")
    print(f"  연산 시간      : {ta + tb:.6f} ms (A+B 합계)")
    print(f"  판정 결과      : {result}\n")
 
 
# ───────────────────────── 메뉴 2: data.json 분석 ─────────────────────────
def normalize_label(x):
    """라벨 표기 흔들림(+, cross, X 등)을 Cross / X 로 통일. 모르면 None."""
    if not isinstance(x, str):
        return None
    s = x.strip().lower()
    if s in ("+", "cross"):
        return "Cross"
    if s == "x":
        return "X"
    return None
 
 
def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)
 
 
def get_filters(data, size):
    """filters.size_N 에서 cross / x 필터를 읽는다."""
    entry = data["filters"][f"size_{size}"]
    keys = {normalize_label(k): v for k, v in entry.items()}
    if "Cross" not in keys or "X" not in keys:
        raise KeyError(f"size_{size} 필터에 cross/x 라벨이 없습니다.")
    return Matrix.from_rows(keys["Cross"]), Matrix.from_rows(keys["X"])
 
 
def analyze_data():
    """모든 패턴을 판정하고 결과 리스트를 반환한다."""
    data = load_data()
    results = []
    filters = {}
    for case_id, case in data.get("patterns", {}).items():
        res = {"id": case_id, "judge": "-", "expected": "-", "status": "FAIL",
               "reason": "", "score_cross": None, "score_x": None}
        try:
            size = int(case_id.split("_")[1])            # size_5_1 -> 5
            if size not in filters:
                filters[size] = get_filters(data, size)
            f_cross, f_x = filters[size]
            exp = normalize_label(case.get("expected"))
            res["expected"] = exp if exp else str(case.get("expected"))
            pat = Matrix.from_rows(case["input"])
            if pat.n != size:
                raise ValueError(f"패턴 크기({pat.n})가 필터 크기({size})와 다름")
            if exp is None:
                raise KeyError(f"알 수 없는 expected 라벨: {case.get('expected')!r}")
            sc, _ = timed_mac(pat, f_cross)
            sx, _ = timed_mac(pat, f_x)
            res.update(score_cross=sc, score_x=sx, judge=judge(sc, sx, "Cross", "X", "UNDECIDED"))
            if res["judge"] == exp:
                res["status"] = "PASS"
            elif res["judge"] == "UNDECIDED":
                res["reason"] = "동점(|차이|<EPSILON) → 판정불가"
            else:
                res["reason"] = f"판정 불일치 (판정={res['judge']}, expected={exp})"
        except (KeyError, ValueError, IndexError, TypeError) as e:
            res["reason"] = f"스키마/데이터 오류: {e.args[0] if e.args else e}"
        results.append(res)
    return results
 
 
_last_results = None
 
 
def menu_analyze():
    global _last_results
    try:
        _last_results = analyze_data()
    except FileNotFoundError:
        print("data.json 이 없습니다. 먼저 `python make_data.py` 로 샘플을 생성하세요.\n")
        return
    except json.JSONDecodeError as e:
        print(f"data.json 파싱 오류: {e}\n")
        return
    print(f"\n{'케이스':<12}{'Cross점수':>11}{'X점수':>11}  {'판정':<10}{'expected':<9}결과")
    print("-" * 62)
    for r in _last_results:
        sc = f"{r['score_cross']:.3f}" if r["score_cross"] is not None else "-"
        sx = f"{r['score_x']:.3f}" if r["score_x"] is not None else "-"
        print(f"{r['id']:<12}{sc:>11}{sx:>11}  {r['judge']:<10}{r['expected']:<9}{r['status']}")
    print()
 
 
# ───────────────────────── 메뉴 3: 성능 분석 ─────────────────────────
def make_test_matrices(n):
    p, f = Matrix(n), Matrix(n)
    for i in range(n):
        for j in range(n):
            p.set(i, j, float((i * 7 + j * 3) % 5))
            f.set(i, j, 1.0 if i == j or i + j == n - 1 else 0.0)
    return p, f
 
 
def menu_performance():
    print(f"\n{'크기':<8}{'평균 시간(ms)':>16}{'연산횟수(N²)':>16}   (각 {PERF_REPEAT}회 반복)")
    print("-" * 52)
    for n in PERF_SIZES:
        p, f = make_test_matrices(n)
        mac(p, f)                                  # 워밍업(측정 제외)
        total = 0.0
        for _ in range(PERF_REPEAT):
            _, t = timed_mac(p, f)
            total += t
        print(f"{f'{n}x{n}':<8}{total / PERF_REPEAT:>16.6f}{n * n:>16}")
    print()
 
 
# ───────────────────────── 메뉴 4: 결과 리포트 ─────────────────────────
def menu_report():
    global _last_results
    if _last_results is None:
        try:
            _last_results = analyze_data()
        except (FileNotFoundError, json.JSONDecodeError):
            print("data.json 을 읽을 수 없어 리포트를 만들 수 없습니다.\n")
            return
    total = len(_last_results)
    fails = [r for r in _last_results if r["status"] == "FAIL"]
    print("\n===== 결과 리포트 =====")
    print(f"전체 테스트 수: {total}")
    print(f"통과 수       : {total - len(fails)}")
    print(f"실패 수       : {len(fails)}")
    if fails:
        print("실패 케이스 목록:")
        for r in fails:
            print(f"  - {r['id']}: {r['reason']}")
    else:
        print("실패 케이스 없음")
    print()
 
 
# ───────────────────────── 메인 ─────────────────────────
def main():
    actions = {"1": menu_user_input, "2": menu_analyze, "3": menu_performance, "4": menu_report}
    while True:
        print("=== MAC 계산기 ===")
        print("1. 사용자 입력(3×3)\n2. data.json 데이터 분석\n3. 성능분석\n4. 결과 리포트\n5. 종료")
        try:
            choice = input("메뉴 선택: ").strip()
        except EOFError:
            break
        if choice == "5":
            print("종료합니다.")
            break
        action = actions.get(choice)
        if action:
            action()
        else:
            print("1~5 사이의 번호를 입력하세요.\n")
 
 
if __name__ == "__main__":
    main()
 