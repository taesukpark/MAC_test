
 """AI의 MAC(Multiply-Accumulate) 연산을 흉내내는 미니 계산기.

실행:  python main.py [--data 경로] [--repeat 횟수]
"""
import argparse
import json
import os
import re
import time

EPSILON = 1e-9          # 부동소수점 비교 허용 오차 (|A-B| < EPSILON 이면 동점)
DEFAULT_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
DEFAULT_REPEAT = 10    # 성능 측정 반복 횟수 기본값 (과제 최소 기준 10회)
PERF_SIZES = (5, 13, 25)

# 실행 설정 (main() 에서 인자로 덮어씀)
DATA_PATH = DEFAULT_DATA
PERF_REPEAT = DEFAULT_REPEAT


# ───────────────────────── 데이터 구조 ─────────────────────────
class Matrix:
    """n×n 2차원 데이터 (패턴/필터 공용). 3×3, 5×5, 13×13, 25×25 등 임의의 n 지원."""

    def __init__(self, n, fill=0.0):
        self.n = n
        self._d = [[fill] * n for _ in range(n)]

    @classmethod
    def from_rows(cls, rows, where="행렬"):
        if not isinstance(rows, list) or len(rows) == 0:
            raise ValueError(f"{where}: 2차원 리스트가 아니거나 비어 있습니다.")
        n = len(rows)
        for i, r in enumerate(rows):
            if not isinstance(r, list) or len(r) != n:
                got = len(r) if isinstance(r, list) else type(r).__name__
                raise ValueError(f"{where}: {i + 1}번째 행의 열 수가 {got} 입니다. (기대: {n}, n×n 형태여야 함)")
        m = cls(n)
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                try:
                    m.set(i, j, float(v))
                except (TypeError, ValueError):
                    raise ValueError(f"{where}: [{i + 1}행 {j + 1}열] 값 {v!r} 은(는) 숫자가 아닙니다.")
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
    """MAC 연산 구간만 측정한다. (입력·파일 읽기·출력 등 I/O 시간은 제외)"""
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
    """n줄을 입력받는다. 형식 오류 시 어느 줄이 문제인지 안내 후 처음부터 재입력."""
    while True:
        print(f"{title} ({n}x{n}) 를 입력하세요. 각 줄에 {n}개의 숫자를 공백으로 구분:")
        rows, ok = [], True
        for line_no in range(1, n + 1):
            parts = input().split()
            if len(parts) != n:
                print(f"입력 형식 오류: 각 줄에 {n}개의 숫자를 공백으로 구분해 입력하세요. "
                      f"({line_no}번째 줄: {len(parts)}개 입력됨)")
                ok = False
                break
            try:
                rows.append([float(x) for x in parts])
            except ValueError:
                print(f"입력 형식 오류: 숫자만 입력할 수 있습니다. ({line_no}번째 줄 숫자 파싱 실패)")
                ok = False
                break
        if ok:
            return Matrix.from_rows(rows, title)


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
    # 대화형 모드는 A/B, data.json 모드는 Cross/X 로 표기하되 동점은 UNDECIDED 로 맞춘다.
    result = judge(sa, sb, "A", "B", "판정불가(UNDECIDED)")
    print("\n[결과]")
    print(f"  필터 A MAC 점수: {sa:.4f}")
    print(f"  필터 B MAC 점수: {sb:.4f}")
    print(f"  I/O 제외 연산 시간: {ta + tb:.6f} ms (필터 A+B MAC 합계, 입력/출력 시간 미포함)")
    print(f"  판정 결과      : {result}\n")


# ───────────────────────── 메뉴 2: data.json 분석 ─────────────────────────
def normalize_label(x):
    """라벨 표기 흔들림(+, plus, cross, X 등)을 Cross / X 로 통일. 모르면 None.
    새 라벨을 추가하려면 여기에 분기를 추가하고 README 체크리스트를 따른다."""
    if not isinstance(x, str):
        return None
    s = x.strip().lower()
    if s in ("+", "plus", "cross"):
        return "Cross"
    if s == "x":
        return "X"
    return None


def need(d, key, where):
    """딕셔너리에서 키를 꺼내되, 없으면 '어디에 어떤 키가 없는지' 를 알려 준다."""
    if not isinstance(d, dict):
        raise KeyError(f"{where} 가 객체(dict)가 아닙니다. (실제 타입: {type(d).__name__})")
    if key not in d:
        raise KeyError(f"{where} 에 키 '{key}' 가 없습니다. 존재하는 키: {list(d.keys())}")
    return d[key]


def load_data():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def find_size(case_id, case):
    """패턴 크기 결정. 1순위: 키 이름 'size_N...'  2순위(대체 매핑): input 의 행 수."""
    m = re.match(r"size_(\d+)", case_id)
    if m:
        return int(m.group(1))
    rows = need(case, "input", f"patterns.{case_id}")
    if isinstance(rows, list) and rows:
        return len(rows)
    raise ValueError(f"patterns.{case_id}: 키에서 크기를 읽을 수 없고 input 도 비어 있습니다.")


def get_filters(data, size):
    """filters 에서 해당 크기의 cross / x 필터를 읽는다. (size_N, N, NxN 키 모두 허용)"""
    filters = need(data, "filters", "data.json")
    entry = None
    for cand in (f"size_{size}", str(size), f"{size}x{size}"):
        if cand in filters:
            entry = filters[cand]
            where = f"filters.{cand}"
            break
    if entry is None:
        raise KeyError(f"filters 에 {size}×{size} 필터 키(size_{size} / {size} / {size}x{size})가 없습니다. "
                       f"존재하는 키: {list(filters.keys())}")
    by_label = {normalize_label(k): v for k, v in entry.items()}
    for label in ("Cross", "X"):
        if label not in by_label:
            raise KeyError(f"{where} 에 {label} 필터 키(cross/+/x)가 없습니다. 존재하는 키: {list(entry.keys())}")
    return (Matrix.from_rows(by_label["Cross"], f"{where}.cross"),
            Matrix.from_rows(by_label["X"], f"{where}.x"))


def analyze_data():
    """모든 패턴을 판정하고 결과 리스트를 반환한다."""
    data = load_data()
    patterns = need(data, "patterns", "data.json")      # 최상위 구조 오류는 호출자에게 전달
    need(data, "filters", "data.json")
    results = []
    filters = {}
    for case_id, case in patterns.items():
        res = {"id": case_id, "judge": "-", "expected": "-", "status": "FAIL",
               "reason": "", "score_cross": None, "score_x": None}
        try:
            size = find_size(case_id, case)
            if size not in filters:
                filters[size] = get_filters(data, size)
            f_cross, f_x = filters[size]
            raw_exp = need(case, "expected", f"patterns.{case_id}")
            exp = normalize_label(raw_exp)
            res["expected"] = exp if exp else str(raw_exp)
            pat = Matrix.from_rows(need(case, "input", f"patterns.{case_id}"), f"patterns.{case_id}.input")
            if pat.n != size:
                raise ValueError(f"패턴 크기({pat.n})가 필터 크기({size})와 다름")
            if exp is None:
                raise KeyError(f"patterns.{case_id}.expected 의 라벨 {raw_exp!r} 을(를) 알 수 없습니다. "
                               f"(허용: +, plus, cross, x)")
            sc, _ = timed_mac(pat, f_cross)
            sx, _ = timed_mac(pat, f_x)
            res.update(score_cross=sc, score_x=sx, judge=judge(sc, sx, "Cross", "X", "UNDECIDED"))
            if res["judge"] == exp:
                res["status"] = "PASS"
            elif res["judge"] == "UNDECIDED":
                res["reason"] = "동점(|차이|<EPSILON) → UNDECIDED"
            else:
                res["reason"] = f"판정 불일치 (판정={res['judge']}, expected={exp})"
        except (KeyError, ValueError, IndexError, TypeError) as e:
            res["reason"] = f"스키마/데이터 오류: {e.args[0] if e.args else e}"
        results.append(res)
    return results


_last_results = None


def run_analysis():
    """분석을 실행하고 결과를 반환. 실패하면 구체적 원인을 출력하고 None."""
    try:
        return analyze_data()
    except FileNotFoundError:
        print(f"data.json 을 찾을 수 없습니다: {DATA_PATH}\n"
              f"  → 경로를 확인하거나 `python main.py --data 파일경로` 로 지정하세요.\n")
    except json.JSONDecodeError as e:
        print(f"data.json 파싱 오류: {e.lineno}번째 줄 {e.colno}번째 칸 — {e.msg}\n")
    except KeyError as e:
        print(f"data.json 구조 오류: {e.args[0]}\n")
    return None


def menu_analyze():
    global _last_results
    results = run_analysis()
    if results is None:
        return
    _last_results = results
    print(f"\n{'케이스':<12}{'Cross점수':>11}{'X점수':>11}  {'판정':<10}{'expected':<9}결과")
    print("-" * 62)
    for r in results:
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
    print(f"\n{'크기':<8}{'평균 시간(ms)':>16}{'연산횟수(N²)':>16}   (각 {PERF_REPEAT}회 반복, I/O 제외 연산 시간)")
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
        print("(메뉴 2 결과가 없어 data.json 을 먼저 분석합니다.)")
        _last_results = run_analysis()
        if _last_results is None:
            return
    total = len(_last_results)
    fails = [r for r in _last_results if r["status"] == "FAIL"]
    passed = total - len(fails)
    pct = (lambda x: f"{x / total * 100:.1f}%" if total else "-")
    print("\n===== 결과 리포트 =====")
    print(f"전체 테스트 수: {total}")
    print(f"통과 수       : {passed} ({pct(passed)})")
    print(f"실패 수       : {len(fails)} ({pct(len(fails))})")
    if fails:
        print("실패 케이스 목록:")
        for r in fails:
            print(f"  - {r['id']}: {r['reason']}")
    else:
        print("실패 케이스 없음")
    print()


# ───────────────────────── 메인 ─────────────────────────
def main():
    global DATA_PATH, PERF_REPEAT
    ap = argparse.ArgumentParser(description="MAC 계산기")
    ap.add_argument("--data", default=DEFAULT_DATA, help="data.json 경로 (기본: main.py 와 같은 폴더)")
    ap.add_argument("--repeat", type=int, default=DEFAULT_REPEAT,
                    help=f"성능 측정 반복 횟수 (기본 {DEFAULT_REPEAT}, 과제 최소 기준 10)")
    args = ap.parse_args()
    if args.repeat < 1:
        ap.error("--repeat 는 1 이상의 정수여야 합니다.")
    DATA_PATH, PERF_REPEAT = args.data, args.repeat

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
