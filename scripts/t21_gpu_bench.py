"""12번 GPU 커널 검증 — CPU 참조 대비 동등성 + 벤치마크.

사용: /home/sieg/projects-wsl/hongik_univ_26_2/.venv/bin/python scripts/t21_gpu_bench.py [--quick]
산출: research/k200_cusum_controlled_12/evidence/gpu_validation.json · research/k200_cusum_controlled_12/GPU_CPU_BENCHMARK.md
판정: float64 에서 rolling 경보 뒤집힘 0 · NaN 패턴 일치 · Page 경보 배열 완전 일치 → GPU_FLOAT64_EQUIVALENT.
      float32 는 뒤집힘이 하나라도 있으면 NUMERICAL_DISAGREEMENT (사용 금지).
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from r2h.k200_controlled import core as C  # noqa: E402
from r2h.k200_controlled import gpu as G  # noqa: E402
from r2h.svrgarch_etf.rolling import MIN_VALID_FRAC, rolling_cusum  # noqa: E402

OUT_DIR = ROOT / "research" / "k200_cusum_controlled_12"
SEED = 20261019
N = 1473
LAM = 2.0
DEV = G.default_device()


# ── 환경 · 경합 기록 ───────────────────────────────────────────────


def smi() -> dict | None:
    """nvidia-smi 한 줄 스냅샷 (사용률 %, 사용 MiB, 전체 MiB)."""
    try:
        q = "utilization.gpu,memory.used,memory.total,name"
        s = subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[0]
        u, mu, mt, name = [x.strip() for x in s.split(",")]
        return {"util_pct": int(u), "mem_used_mib": int(mu), "mem_total_mib": int(mt), "name": name}
    except Exception as ex:  # nvidia-smi 없음 · 실패는 기록만
        return {"error": repr(ex)}


class SmiPoller:
    """GPU 측정 동안 0.5 초마다 nvidia-smi 사용률을 모은다."""

    def __init__(self) -> None:
        self.rows: list[dict] = []
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            r = smi()
            if r and "util_pct" in r:
                self.rows.append(r)
            self._stop.wait(0.5)

    def __enter__(self):
        self._th.start()
        return self

    def __exit__(self, *a) -> None:
        self._stop.set()
        self._th.join()

    def summary(self) -> dict:
        if not self.rows:
            return {"samples": 0}
        u = [r["util_pct"] for r in self.rows]
        m = [r["mem_used_mib"] for r in self.rows]
        return {"samples": len(u), "util_max": max(u), "util_median": float(np.median(u)), "mem_used_mib_max": max(m)}


def load_snapshot() -> dict:
    """CPU 부하 · 동시 실행 중인 MC 프로세스 (CPU 측정 오염 여부 판단용)."""
    up = subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()
    ps = subprocess.run(["pgrep", "-af", "run_t21_mc|run_t2[0-9]_pipeline"], capture_output=True, text=True).stdout
    procs = [p for p in ps.strip().splitlines() if p and "pgrep" not in p and "bash -c" not in p]
    return {"uptime": up, "mc_procs": procs}


def sync() -> None:
    if DEV.type == "cuda":
        torch.cuda.synchronize()


def time_gpu(fn, reps: int = 3) -> tuple[float, int]:
    """warm-up 1 회 제외, 동기화 후 반복 median 초 · 최대 할당 바이트."""
    fn()
    sync()
    if DEV.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        sync()
        ts.append(time.perf_counter() - t0)
    peak = torch.cuda.max_memory_allocated() if DEV.type == "cuda" else 0
    if DEV.type == "cuda":
        torch.cuda.empty_cache()  # 캐시를 돌려줘 다른 세션의 여유 VRAM 을 잠식하지 않음
    return float(np.median(ts)), int(peak)


def time_cpu(fn, reps: int = 3) -> float:
    """첫 실행이 1 초를 넘으면 1 회만, 아니면 reps 회 median."""
    t0 = time.perf_counter()
    fn()
    t = time.perf_counter() - t0
    if t > 1.0 or reps == 1:
        return t
    ts = [t]
    for _ in range(reps - 1):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return float(np.median(ts))


# ── 입력 ──────────────────────────────────────────────────────────


def make_data(kind: str, R: int, n: int = N, seed: int = SEED) -> np.ndarray:
    """t5 · normal · t5_nan (랜덤 3% NaN + 긴 NaN 구간 · ±1 행 (τ̂²=0) · 전부 NaN 행)."""
    rng = np.random.default_rng([seed, R, n, {"t5": 0, "normal": 1, "t5_nan": 2}[kind]])
    if kind == "normal":
        return rng.standard_normal((R, n))
    E = rng.standard_t(5, (R, n))
    if kind == "t5_nan":
        E[rng.random((R, n)) < 0.03] = np.nan
        E[0, 300:340] = np.nan  # 40 일 연속 (w=252 의 0.1w 초과, w=20/60 은 창 전체)
        E[3, 700:727] = np.nan  # 27 일 연속 (w=252 의 min_valid 경계 근처)
        E[1] = np.where(rng.random(n) < 0.5, -1.0, 1.0)  # τ̂² 정확히 0 → NaN
        E[2] = np.nan  # 전부 NaN
    return E


def cpu_rolling(E: np.ndarray, w: int) -> np.ndarray:
    """CPU 참조 — 경로마다 ``rolling_cusum`` (실제 파이프라인과 같은 호출)."""
    return np.stack([rolling_cusum(e, w) for e in E])


def cpu_page_grid(E, lam, H, rm) -> np.ndarray:
    """CPU 참조 — h 마다 ``page_alarm_batch`` 반복 → (R, K, n)."""
    return np.stack([C.page_alarm_batch(E, lam, float(h), rm) for h in H], axis=1)


def cmp_rolling(cpu: np.ndarray, g: np.ndarray) -> dict:
    """최대 절대오차 · NaN 패턴 불일치 · CPU T 95% 분위 임계에서의 경보 뒤집힘 수."""
    nc, ng = np.isnan(cpu), np.isnan(g)
    both = ~nc & ~ng
    crit = float(np.nanquantile(cpu, 0.95))
    flips = int(((cpu[both] >= crit) != (g[both] >= crit)).sum())
    return {
        "max_abs_err": float(np.max(np.abs(cpu[both] - g[both]))) if both.any() else 0.0,
        "nan_mismatch": int((nc != ng).sum()), "crit_q95_cpu": crit, "flips_at_q95": flips,
        "n_finite": int(both.sum()),
    }


# ── 동등성 ────────────────────────────────────────────────────────


def equivalence() -> dict:
    out: dict = {"rolling": [], "rolling_segmented": None, "page": [], "block_hits": [], "block_max": None}
    R = 200
    for kind in ("t5", "normal", "t5_nan"):
        E = make_data(kind, R)
        for w in (20, 60, 252):
            cpu = cpu_rolling(E, w)
            g64 = G.rolling_cos_batch(E, w, dtype=torch.float64).cpu().numpy()
            g32 = G.rolling_cos_batch(E, w, dtype=torch.float32).cpu().numpy().astype(np.float64)
            out["rolling"].append({"data": kind, "w": w, "R": R, "n": N,
                                   "float64": cmp_rolling(cpu, g64), "float32": cmp_rolling(cpu, g32)})
    E = make_data("t5_nan", R)
    resets = [400, 900]
    cpu = np.stack([C.rolling_segmented(e, 60, resets) for e in E])
    g = G.rolling_segmented_batch(E, 60, resets).cpu().numpy()
    out["rolling_segmented"] = {"data": "t5_nan", "w": 60, "resets": resets, "float64": cmp_rolling(cpu, g)}

    H = np.linspace(0.5, 20.0, 64)
    bid = np.minimum(np.arange(N) // 246, 5)
    bid[:30] = -1  # 블록 밖 날 포함
    for kind, with_reset in (("t5", False), ("t5_nan", True)):
        E = make_data(kind, R)
        rng = np.random.default_rng([SEED, 7])
        rm = (rng.random(E.shape) < 0.01) if with_reset else None
        inc_cpu = C.page_increment(E, LAM)
        inc_gpu = G.page_increment_t(torch.as_tensor(E, device=DEV), LAM).cpu().numpy()
        cpu = cpu_page_grid(E, LAM, H, rm)
        g64 = G.page_alarm_grid(E, LAM, H, rm, dtype=torch.float64).cpu().numpy()
        g32 = G.page_alarm_grid(E, LAM, H, rm, dtype=torch.float32).cpu().numpy()
        out["page"].append({
            "data": kind, "reset_mask": with_reset, "lam": LAM, "K": len(H), "R": R, "n": N,
            "inc_bit_equal": bool(np.array_equal(inc_cpu, inc_gpu, equal_nan=True)),
            "n_alarms_cpu": int(cpu.sum()),
            "float64_exact": bool(np.array_equal(cpu, g64)), "float64_flips": int((cpu != g64).sum()),
            "float32_flips": int((cpu != g32).sum()),
        })
        ref_bh = np.stack([cpu[:, :, bid == b].any(axis=2) for b in range(6)], axis=2)
        bh = G.page_block_hits(E, LAM, H, rm, bid, 6).cpu().numpy()
        out["block_hits"].append({"data": kind, "float64_exact": bool(np.array_equal(ref_bh, bh))})
    T = cpu_rolling(make_data("t5_nan", R), 60)
    ref = C.block_max(T, [bid == b for b in range(6)])
    g = G.block_max(torch.as_tensor(T, device=DEV), bid, 6).cpu().numpy()
    out["block_max"] = {"exact": bool(np.array_equal(ref, g, equal_nan=True))}
    return out


def oom_retry_check() -> dict:
    """실제 OOM 을 내지 않고 chunk > 50 에서 OutOfMemoryError 를 흉내 → 절반 재시도로 같은 결과인지."""
    E = make_data("t5_nan", 200)
    ref = G.rolling_cos_batch(E, 20).cpu().numpy()
    orig = G._rolling_chunk

    def flaky(X, w, mv):
        if X.shape[0] > 50:
            raise torch.cuda.OutOfMemoryError("simulated")
        return orig(X, w, mv)

    G._rolling_chunk = flaky
    try:
        got = G.rolling_cos_batch(E, 20, chunk=200).cpu().numpy()
    finally:
        G._rolling_chunk = orig
    return {"equal": bool(np.array_equal(ref, got, equal_nan=True)), **G.LAST_RUN}


# ── 벤치 ──────────────────────────────────────────────────────────


def bench_rolling(Rs, ws) -> list[dict]:
    rows = []
    for w in ws:
        for R in Rs:
            E = make_data("t5", R)
            holder = {}
            t_cpu = time_cpu(lambda: holder.__setitem__("c", cpu_rolling(E, w)))
            t_gpu, peak = time_gpu(lambda: holder.__setitem__("g", G.rolling_cos_batch(E, w).cpu().numpy()))
            cmp64 = cmp_rolling(holder["c"], holder["g"])  # 다중 chunk 경로도 동등성 확인
            rows.append({"float64_flips": cmp64["flips_at_q95"], "float64_nan_mismatch": cmp64["nan_mismatch"],
                         "float64_max_abs_err": cmp64["max_abs_err"],"w": w, "R": R, "cpu_s": t_cpu, "gpu_s": t_gpu, "speedup": t_cpu / t_gpu,
                         "cpu_ms_per_path": 1e3 * t_cpu / R, "gpu_ms_per_path": 1e3 * t_gpu / R,
                         "gpu_peak_mib": peak / 2**20, "chunk": G.LAST_RUN.get("chunk"),
                         "oom_retries": G.LAST_RUN.get("oom_retries"), "smi_after": smi()})
            print(f"rolling w={w} R={R}: cpu {t_cpu:.3f}s gpu {t_gpu:.3f}s ×{t_cpu / t_gpu:.1f}", flush=True)
    return rows


def bench_page(R, Ks) -> list[dict]:
    rows = []
    E = make_data("t5", R)
    rm = np.random.default_rng([SEED, 8]).random(E.shape) < 0.01
    bid = np.minimum(np.arange(N) // 246, 5)
    for K in Ks:
        H = np.linspace(0.5, 20.0, K)
        t0 = time.perf_counter()
        cpu = cpu_page_grid(E, LAM, H, rm)
        t_cpu = time.perf_counter() - t0
        t_tile = None
        if K <= 64:  # K 를 행으로 펼친 한 번 호출 (메모리 R·K·n float64)
            Et, rmt, ht = np.repeat(E, K, axis=0), np.repeat(rm, K, axis=0), np.tile(H, R)
            t0 = time.perf_counter()
            C.page_alarm_batch(Et, LAM, ht, rmt)
            t_tile = time.perf_counter() - t0
            del Et, rmt
        holder = {}
        t_gpu, peak = time_gpu(lambda: holder.__setitem__("a", G.page_alarm_grid(E, LAM, H, rm).cpu().numpy()))
        t_blk, peak_b = time_gpu(lambda: G.page_block_hits(E, LAM, H, rm, bid, 6).cpu().numpy())
        best_cpu = min(t_cpu, t_tile) if t_tile else t_cpu
        rows.append({"R": R, "K": K, "n": N, "cpu_loop_s": t_cpu, "cpu_tiled_s": t_tile, "gpu_grid_s": t_gpu,
                     "gpu_block_s": t_blk, "speedup_grid": best_cpu / t_gpu, "speedup_block": best_cpu / t_blk,
                     "gpu_peak_mib": max(peak, peak_b) / 2**20, "float64_exact": bool(np.array_equal(cpu, holder["a"])),
                     "smi_after": smi()})
        print(f"page K={K}: cpu {t_cpu:.2f}s tiled {t_tile} gpu {t_gpu:.3f}s blk {t_blk:.3f}s", flush=True)
    return rows


# ── 판정 · 기록 ───────────────────────────────────────────────────


def verdicts(eq: dict, br: list[dict], bp: list[dict]) -> dict:
    r64 = eq["rolling"] + [eq["rolling_segmented"]]
    ok64 = (all(r["float64"]["flips_at_q95"] == 0 and r["float64"]["nan_mismatch"] == 0 for r in r64)
            and all(p["float64_exact"] for p in eq["page"]) and all(b["float64_exact"] for b in eq["block_hits"])
            and eq["block_max"]["exact"] and all(b["float64_exact"] for b in bp)
            and all(r["float64_flips"] == 0 and r["float64_nan_mismatch"] == 0 for r in br))
    f32 = sum(r["float32"]["flips_at_q95"] + r["float32"]["nan_mismatch"] for r in eq["rolling"]) + sum(
        p["float32_flips"] for p in eq["page"])
    return {"float64": "GPU_FLOAT64_EQUIVALENT" if ok64 else "GPU_FLOAT64_NOT_EQUIVALENT",
            "float32": "NUMERICAL_DISAGREEMENT" if f32 > 0 else "FLOAT32_NO_FLIP_OBSERVED",
            "float32_total_flips": int(f32)}


def write_md(res: dict) -> str:
    v, eq = res["verdict"], res["equivalence"]
    L = ["# GPU · CPU 동등성과 벤치마크 (12번, T21)", "",
         f"- 생성: {res['generated_utc']} · `scripts/t21_gpu_bench.py` · 시드 {SEED} · n={N} · λ={LAM}",
         f"- 장치: {res['env']['gpu_name']} · torch {res['env']['torch']} · numpy {res['env']['numpy']} · Python {res['env']['python']}",
         f"- VRAM 예산 = min(6 GB, 여유−2 GB) = {res['env']['budget_gib']:.2f} GiB (시작 시 여유 {res['env']['free_gib_start']:.2f} GiB)",
         f"- 커널: `src/r2h/k200_controlled/gpu.py` (numpy·torch 만 import)", "",
         "## 판정", "",
         f"- **float64: `{v['float64']}`** — rolling 경보 뒤집힘 0 · NaN 패턴 일치 · Page 경보 배열 완전 일치가 모두 성립해야 함",
         f"- **float32: `{v['float32']}`** (뒤집힘 합 {v['float32_total_flips']}) — " +
         ("사용 금지" if v["float32"] == "NUMERICAL_DISAGREEMENT" else "이번 입력에서 뒤집힘 없음 (그래도 기본은 float64)"), "",
         "## 동등성 — 이동창 CoS (R=200, 임계 = CPU T 의 95% 분위)", "",
         "| 데이터 | w | f64 최대 절대오차 | f64 NaN 불일치 | f64 뒤집힘 | f32 최대 절대오차 | f32 NaN 불일치 | f32 뒤집힘 |",
         "|---|---|---|---|---|---|---|---|"]
    for r in eq["rolling"]:
        a, b = r["float64"], r["float32"]
        L.append(f"| {r['data']} | {r['w']} | {a['max_abs_err']:.2e} | {a['nan_mismatch']} | {a['flips_at_q95']} | "
                 f"{b['max_abs_err']:.2e} | {b['nan_mismatch']} | {b['flips_at_q95']} |")
    s = eq["rolling_segmented"]
    L += ["", f"- 분할 (resets {s['resets']}, w=60, t5_nan): f64 최대 절대오차 {s['float64']['max_abs_err']:.2e}, "
              f"NaN 불일치 {s['float64']['nan_mismatch']}, 뒤집힘 {s['float64']['flips_at_q95']}", "",
          "## 동등성 — Page CUSUM 격자 (R=200, K=64, h∈[0.5, 20])", "",
          "| 데이터 | reset_mask | 증분 비트 일치 | CPU 경보 수 | f64 완전 일치 | f64 뒤집힘 | f32 뒤집힘 |", "|---|---|---|---|---|---|---|"]
    for p in eq["page"]:
        L.append(f"| {p['data']} | {p['reset_mask']} | {p['inc_bit_equal']} | {p['n_alarms_cpu']} | {p['float64_exact']} | "
                 f"{p['float64_flips']} | {p['float32_flips']} |")
    L += ["", f"- 블록 집계 `page_block_hits` (6 블록, 블록 밖 날 포함): " +
          ", ".join(f"{b['data']} 일치 {b['float64_exact']}" for b in eq["block_hits"]),
          f"- `block_max` (NaN 무시) vs `core.block_max`: 일치 {eq['block_max']['exact']}",
          f"- OOM 재시도 (chunk>50 에서 OOM 흉내, chunk 200 시작): 결과 일치 {res['oom_retry']['equal']}, "
          f"재시도 {res['oom_retry']['oom_retries']} 회, 최종 chunk {res['oom_retry']['chunk']}", "",
          "## 벤치 — 이동창 CoS (t5, end-to-end: numpy→GPU→numpy, GPU 는 warm-up 제외 3 회 median)", "",
          "CPU 기준 = 경로마다 `rolling_cusum` (실제 파이프라인 호출 방식).", "",
          "| w | R | CPU s | GPU s | 속도비 | CPU ms/경로 | GPU ms/경로 | 최대 VRAM MiB | chunk | OOM 재시도 | f64 뒤집힘 | f64 최대오차 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in res["bench_rolling"]:
        L.append(f"| {r['w']} | {r['R']} | {r['cpu_s']:.3f} | {r['gpu_s']:.3f} | {r['speedup']:.1f}× | "
                 f"{r['cpu_ms_per_path']:.2f} | {r['gpu_ms_per_path']:.3f} | {r['gpu_peak_mib']:.0f} | {r['chunk']} | {r['oom_retries']} | "
                 f"{r['float64_flips']} | {r['float64_max_abs_err']:.1e} |")
    L += ["", "## 벤치 — Page 격자 (R=1000, n=1473, reset 1%)", "",
          "CPU = h 마다 `page_alarm_batch` 반복 (K≤64 는 K 를 행으로 펼친 1 회 호출도 측정, 더 빠른 쪽을 속도비 기준).", "",
          "| K | CPU 반복 s | CPU 펼침 s | GPU 격자 s | GPU 블록집계 s | 속도비 격자 | 속도비 블록 | 최대 VRAM MiB | f64 일치 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in res["bench_page"]:
        tt = f"{r['cpu_tiled_s']:.2f}" if r["cpu_tiled_s"] else "—"
        L.append(f"| {r['K']} | {r['cpu_loop_s']:.2f} | {tt} | {r['gpu_grid_s']:.3f} | {r['gpu_block_s']:.3f} | "
                 f"{r['speedup_grid']:.1f}× | {r['speedup_block']:.1f}× | {r['gpu_peak_mib']:.0f} | {r['float64_exact']} |")
    c = res["contention"]
    L += ["", "## 경합 · 측정 조건", "",
          f"- 시작 nvidia-smi: {c['smi_start']}", f"- 끝 nvidia-smi: {c['smi_end']}",
          f"- GPU 측정 중 폴링: {c['smi_during']}",
          f"- CPU 부하 시작: `{c['load_start']['uptime']}` · 끝: `{c['load_end']['uptime']}`",
          f"- 동시 실행 MC 프로세스: {len(c['load_start']['mc_procs'])} (시작) / {len(c['load_end']['mc_procs'])} (끝)"
          + (" — **CPU 측정값이 오염되었을 수 있음**" if c["load_start"]["mc_procs"] or c["load_end"]["mc_procs"] else ""),
          "- nvidia-smi 메모리에는 이 프로세스의 torch 캐시 (reserved) 도 포함된다 — 최대 VRAM 은 `max_memory_allocated` 기준",
          "- GPU 는 다른 세션과 공유 중일 수 있다 (시작 시 사용률이 0 이 아니면 GPU 시간은 보수적 값).",
          "- 참고: 다른 세션이 GPU 를 98% (median) 쓰던 중의 실행 (`evidence/gpu_validation_contended_run.json`) 에서는 "
          "w=60 R=1500 (0.4×) · w=252 R=1024 (0.4×) 가 CPU 보다 느렸다 (동등성은 같음). 경합 중에는 GPU 이득이 사라질 수 있다", "",
          "## 권고", ""]
    L += [f"- {x}" for x in res["recommendation"]]
    L += ["", f"- 전체 최대 VRAM (torch max_memory_allocated): {res['max_vram_mib']:.0f} MiB", ""]
    return "\n".join(L)


def recommend(res: dict) -> list[str]:
    rec = []
    if res["verdict"]["float64"] != "GPU_FLOAT64_EQUIVALENT":
        return ["float64 동등성 불성립 — GPU 결과를 판정에 쓰지 말 것 (CPU 사용). 불일치 항목은 위 표 참조"]
    slow = [f"w={r['w']} R={r['R']}" for r in res["bench_rolling"] if r["speedup"] < 1]
    fast = [r for r in res["bench_rolling"] if r["speedup"] >= 1]
    if fast:
        rec.append("이동창 CoS 대량 경로 (귀무 MC 임계값·블록 최대): GPU float64 사용 — 속도비 "
                   f"{min(r['speedup'] for r in fast):.1f}×–{max(r['speedup'] for r in fast):.1f}×")
    if slow:
        rec.append("GPU 가 더 느린 조합 → CPU 사용: " + ", ".join(slow))
    for r in res["bench_page"]:
        tag = "GPU" if r["speedup_block"] >= 1 else "CPU 사용"
        rec.append(f"Page h 격자 K={r['K']}: 블록집계 속도비 {r['speedup_block']:.1f}× / 격자 {r['speedup_grid']:.1f}× → {tag}")
    rec.append("Page h 이분 탐색 (`calibrate_page_h`) 은 K 후보 격자 `page_block_hits` 한 번으로 바꾸면 GPU 이득이 크다 (단 K≥64)")
    if res["verdict"]["float32"] == "NUMERICAL_DISAGREEMENT":
        rec.append("float32 는 사용 금지 (경보 뒤집힘 관측)")
    rec.append("Page·블록 집계는 CPU 와 비트 일치, 이동창 T 는 비트 일치가 아님 (최대 절대오차 ~1e-14) — 임계값과 T 는 같은 backend 에서 계산할 것")
    rec.append("GPU 는 동시에 한 작업만 — 다른 세션과 겹치면 예산 min(6 GB, 여유−2 GB) 가 줄어 chunk 가 작아진다")
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="작은 벤치 (개발용)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR, help="산출 폴더 (기본 research/k200_cusum_controlled_12)")
    a = ap.parse_args()
    assert MIN_VALID_FRAC == G.MIN_VALID_FRAC
    free, total = torch.cuda.mem_get_info() if DEV.type == "cuda" else (0, 0)
    budget = G.vram_budget()
    contention = {"smi_start": smi(), "load_start": load_snapshot()}
    env = {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__,
           "device": str(DEV), "gpu_name": torch.cuda.get_device_name(0) if DEV.type == "cuda" else "cpu",
           "free_gib_start": free / 2**30, "total_gib": total / 2**30, "budget_gib": budget / 2**30}
    print(env, contention, flush=True)
    with SmiPoller() as poll:
        eq = equivalence()
        oom = oom_retry_check()
        Rs = [128, 256] if a.quick else [128, 256, 512, 1024, 1500]
        br = bench_rolling(Rs, [20, 60, 252])
        bp = bench_page(200 if a.quick else 1000, [1, 64] if a.quick else [1, 64, 256])
    contention.update(smi_end=smi(), load_end=load_snapshot(), smi_during=poll.summary())
    res = {"generated_utc": datetime.now(UTC).isoformat(timespec="seconds"), "quick": a.quick, "seed": SEED,
           "env": env, "equivalence": eq, "oom_retry": oom, "bench_rolling": br, "bench_page": bp,
           "contention": contention}
    res["verdict"] = verdicts(eq, br, bp)
    res["max_vram_mib"] = max([r["gpu_peak_mib"] for r in br + bp] + [0])
    res["recommendation"] = recommend(res)
    od = a.out_dir
    (od / "evidence").mkdir(parents=True, exist_ok=True)
    (od / "evidence" / "gpu_validation.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    (od / "GPU_CPU_BENCHMARK.md").write_text(write_md(res), encoding="utf-8")
    print(json.dumps(res["verdict"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
