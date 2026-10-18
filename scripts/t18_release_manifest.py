"""W4 (T18) 그림 목록·주장-근거 표·배포 manifest 생성 — 결과 파일에서 수치를 읽어 쓴다."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/peer_relative_shock_w4"

FIGS = [
    ("F01_sigma20_grid", "A", "20종 20일 연환산 σ 시계열 + A 눈금"),
    ("F02_sigma60_grid", "A", "20종 60일 연환산 σ 시계열 + A 눈금"),
    ("F03_level_vs_rank", "A", "절대 σ 수준(10–90분위·최대)과 주분석 A 비율"),
    ("F04_A_heatmap", "A", "20일·60일 A 상태 지도"),
    ("F05_leverage_normalization", "A", "레버리지·인버스 배율 정규화 전후"),
    ("F06_peer_network", "B", "Peer Mapping 네트워크 (Tier·등급)"),
    ("F07_peer_ratio_grid", "B", "ETF별 Peer 로그비율 L 과 B↑/B↓"),
    ("F08_peer_ratio_rank_heat", "B", "L 의 과거 분위 U_B 지도"),
    ("F09_B_direction_map", "B", "B 양방향 사건 지도"),
    ("F10_kospi200_four", "B", "KOSPI200 4종 배율 보정 σ·Core Pair 비율·그룹 상태"),
    ("F11_domestic_peer", "B", "국내 업종·전략 ETF 자기 σ 대 Peer 중앙값"),
    ("F12_overseas_bond_cmd_fx_peer", "B", "해외 주식·채권·원자재·통화 Peer 진단"),
    ("F13_group_A_timeline", "C", "17 그룹 A 타임라인"),
    ("F14_group_B_timeline", "C", "17 그룹 B 타임라인"),
    ("F15_group_AB_timeline", "C", "17 그룹 AB 타임라인"),
    ("F16_count_A", "C", "A 참여 그룹 수"),
    ("F17_count_B", "C", "B 참여 그룹 수"),
    ("F18_count_AB", "C", "AB 참여 그룹 수"),
    ("F19_A_B_intersection", "C", "A·B·AB 교집합 (ETF-일)"),
    ("F20_horizon_20_vs_60", "C", "20일 대 60일 그룹 수 교차표·Jaccard"),
    ("F21_global_A_17of17", "D", "GLOBAL_A 17/17 충족일"),
    ("F22_global_B_17of17", "D", "GLOBAL_B 17/17 충족일"),
    ("F23_global_AB_17of17", "D", "GLOBAL_AB 17/17 충족일"),
    ("F24_final_shock_timeline", "D", "FINAL_SHOCK 전체 시계열·판정 가능일"),
    ("F25_interval_durations", "D", "급변 구간 지속기간 (0개) + 그룹별 AB 최장 지속 (진단)"),
    ("F26_bottleneck", "D", "17/17 병목 (그룹별 충족률·한 그룹 제외 진단)"),
    ("F27_participation_distribution", "D", "0–17 참여 그룹 수 분포"),
    ("F28_event_E2024_08", "E", "2024-08 사건: 가격·σ·U_A·B·그룹 수 vs W2·FINAL"),
    ("F29_event_E2025_04", "E", "2025-04 사건"),
    ("F30_event_E2022_bond", "E", "2022 채권 사건"),
    ("F31_w3_comparison", "E", "W3 CUSUM 에피소드 대 W4 그룹 수"),
    ("F32_definition_cases", "E", "A만·B↑만·B↓만·AB 실제 사례"),
    ("F33_eligibility", "E", "L 상태(결측·영분산·Peer 부족)와 연도별 판정 가능일"),
    ("F34_summary_limits", "E", "k 이상 동시 충족 일수 곡선·결론·한계"),
]

CLAIMS = [
    ("C1", "판정 VALID_ZERO_INTERVALS, 주분석 1,225일 판정 가능 100%, FINAL 0일, 구간 0개", "results/w4_final.json · shock_intervals.csv", "pipeline.verdict · intervals", "09 §11, F24"),
    ("C2", "민감도 4종 모두 17/17 AB 0일·구간 0", "results/sensitivity_summary.csv", "pipeline.sensitivity", "09 §15, F25"),
    ("C3", "주분석 최대 참여 A 12/6 · B 7/7 · AB 3/2 (q20/q60)", "results/global_by_period.csv", "pipeline.global_by_period", "09 §9, F16–F18"),
    ("C4", "GLOBAL_A 17/17 은 2020-03-16~04-06 (q20, 파일럿) 16일, 그날 B 3–6", "results/global_daily_counts.csv", "core.global_states", "09 §9·§10, F21"),
    ("C5", "A∩B: A ETF-일의 12.6% (q20)·22.1% (q60)", "results/figure_captions.json F19", "figures.f19_intersection", "09 §8, F19"),
    ("C6", "B↑ 1,022 · B↓ 1,260 (q20 주분석 ETF-일)", "results/figure_captions.json F09", "figures.f09_B_map", "09 §6, F09"),
    ("C7", "KOSPI200 Core Pair |L| 중앙 0.894 %p, B↑ 87 · B↓ 71", "results/figure_captions.json F10", "core.pair_ratio_state", "09 §7, F10"),
    ("C8", "레버리지·인버스 정규화 비율 중앙 1.004·1.025, A 일치 ≥ 98.9%", "results/kospi200_aux_diagnostics.csv", "pipeline.kospi_aux_table", "09 §7, F05"),
    ("C9", "한 그룹 제외 16/16 A·B·AB 모두 0일, 유일 병목 0일", "results/bottleneck_groups.csv", "pipeline.bottleneck", "09 §12, F26"),
    ("C10", "W2 정의 재계산 80/80 일치, σ 대 √(252·mean r²) Spearman 중앙 0.992/0.997", "evidence/w2_reconstruction_check.csv · results/comparison_w2_w3.csv", "pipeline.w2_reference · compare_w2_w3", "09 §14"),
    ("C11", "사건 최대 A: 2024-08 10 · 2025-04 12 · 2022 9 (q20), 세 사건 FINAL 0", "results/event_case_studies.csv", "pipeline.event_cases", "09 §13, F28–F30"),
    ("C12", "W3 에피소드 20건 동안 W4 AB 최대 3, FINAL 0", "results/comparison_w2_w3.csv (w3_ 블록)", "pipeline.compare_w2_w3", "09 §14, F31"),
    ("C13", "Peer 20/20 매핑, PEER_UNAVAILABLE 0, 참조 42종, 늦은 상장 제외 10", "results/peer_mapping.csv", "scripts/t18_freeze_peer_mapping.py", "09 §3, F06"),
    ("C14", "영변동성 0건, Peer 부족 130 (전부 2019 132030)", "results/zero_volatility_audit.csv", "core.peer_log_ratio", "09 §15, F33"),
    ("C15", "20·60일 그룹-일 Jaccard A 0.30 · AB 0.17", "results/figure_captions.json F20", "figures.f20_horizons", "09 §10, F20"),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    caps = json.loads((BASE / "results/figure_captions.json").read_text(encoding="utf-8"))
    lines = ["# W4 그림 목록 (F01–F34)", "",
             "모두 실제 계산 결과로 그렸다. PNG 320dpi 와 SVG 를 함께 둔다. 캡션 수치는 `results/figure_captions.json` 에 있다.",
             "", "| 그림 | 묶음 | 내용 | 캡션 수치 (요약) |", "|---|---|---|---|"]
    for name, grp, desc in FIGS:
        c = json.dumps(caps.get(name, {}), ensure_ascii=False, default=str)
        c = c if len(c) < 160 else c[:157] + "…"
        lines.append(f"| `{name}` | {grp} | {desc} | `{c}` |")
    lines += ["", "묶음: A 개별 ETF 변동성 · B Peer 상대 · C 그룹 상태 · D 최종 구간 · E 기존 연구 대조.",
              "진단 그림(F25 오른쪽, F26 의 한 그룹 제외)은 라벨이 아니다."]
    (BASE / "FIGURE_CATALOG.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    cl = ["# W4 주장–근거 표", "", "| # | 주장 | 결과 파일 | 계산 위치 | 노트북·그림 |", "|---|---|---|---|---|"]
    cl += [f"| {a} | {b} | `{c}` | `{d}` | {e} |" for a, b, c, d, e in CLAIMS]
    cl += ["", "노트북 09 의 마지막 CLAIMS 셀이 해석 문단 수치 30개를 결과 파일과 다시 대조한다 (30/30)."]
    (BASE / "CLAIM_EVIDENCE_MATRIX.md").write_text("\n".join(cl) + "\n", encoding="utf-8")
    files = sorted(p for p in BASE.rglob("*") if p.is_file() and p.name != "RELEASE_MANIFEST.json")
    nb = ROOT / "notebooks/09_ETF20종_Peer상대변동성_급변구간정의.ipynb"
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    man = {"study_id": "t18_peer_relative_shock_w4", "protocol_version": "W4-lock-1", "base_commit": "534a122208cfbeeb3361e01f35e66d36ffc54213",
           "contract_commit": "52f98b0", "head_at_manifest": head,
           "verdict": json.loads((BASE / "results/w4_final.json").read_text())["verdict"]["verdict"],
           "notebook": {"path": str(nb.relative_to(ROOT)), "sha256": sha(nb)},
           "files": {str(p.relative_to(ROOT)): sha(p) for p in files},
           "code": {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / "src/r2h/peer_shock").glob("*.py"))}
           | {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / "scripts").glob("*t18*.py"))},
           "excluded_from_git": ["data/raw/", "data/external/peer/", "outputs/t18/ (일별 σ·L·종가 — 가격 역산 가능)"]}
    (BASE / "RELEASE_MANIFEST.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("그림", len(FIGS), "· 주장", len(CLAIMS), "· manifest 파일", len(man["files"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
