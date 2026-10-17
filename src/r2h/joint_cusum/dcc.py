"""H0-B 귀무: GARCH(1,1)-t 주변 + DCC(1,1)-t / CCC-t 상관 (계약 §6.1–6.3, D3).

NumPy/SciPy 만 쓴다. 2단계 추정:
1. ETF 별 상수 평균 + GARCH(1,1) + 표준화 Student-t 최대우도 (수익률을 표본 sd 로 나눈 척도에서 적합 후 복원).
2. 표준화 잔차 z 로 DCC 의 (a, b, ν_c) 를 다변량 t 최대우도로 적합. 상관 목표 Q̄ = mean(z zᵀ).
최적화가 끝났다는 사실만으로 성공으로 보지 않는다 — ``validity_numeric`` 이 경계·정상성·양정치성을 따로 확인한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, signal, special

NU_LO, NU_HI = 2.1, 200.0
PERSIST_MAX = 0.999
BOUND_TOL = 1e-4


# ── 주변 GARCH(1,1)-t ───────────────────────────────────────────────


def _garch_var(eps: np.ndarray, omega: float, alpha: float, beta: float, h0: float) -> np.ndarray:
    """σ²_t = ω + α ε²_{t−1} + β σ²_{t−1}, σ²_0 = h0 (선형 필터로 계산)."""
    x = np.empty_like(eps)
    x[0] = 0.0
    x[1:] = omega + alpha * eps[:-1] ** 2
    # y_t = x_t + β y_{t−1}, 초기값 y_0 = h0
    y, _ = signal.lfilter([1.0], [1.0, -beta], x[1:], zi=[beta * h0])
    return np.concatenate([[h0], y])


def _t_logpdf_std(z2: np.ndarray, nu: float) -> np.ndarray:
    """분산 1 로 정규화한 Student-t 의 log 밀도 (z² 입력, 척도항 제외)."""
    c = special.gammaln((nu + 1) / 2) - special.gammaln(nu / 2) - 0.5 * np.log(np.pi * (nu - 2))
    return c - (nu + 1) / 2 * np.log1p(z2 / (nu - 2))


@dataclass(frozen=True)
class GarchT:
    mu: float
    omega: float
    alpha: float
    beta: float
    nu: float
    loglik: float
    success: bool
    message: str

    @property
    def persistence(self) -> float:
        return self.alpha + self.beta

    @property
    def uncond_var(self) -> float:
        return self.omega / (1.0 - self.persistence)


def fit_garch_t(r: np.ndarray) -> GarchT:
    """상수 평균 GARCH(1,1)-t 최대우도. 척도 s = sd(r) 로 나눈 뒤 적합하고 ω·μ 를 원 단위로 복원."""
    r = np.asarray(r, float)
    s = float(np.std(r))
    x = r / s
    h0 = float(np.var(x))

    def nll(th: np.ndarray) -> float:
        mu, om, al, be, nu = th
        if al + be >= PERSIST_MAX:
            return 1e10
        eps = x - mu
        h = _garch_var(eps, om, al, be, h0)
        if not np.all(h > 0):
            return 1e10
        ll = _t_logpdf_std(eps**2 / h, nu) - 0.5 * np.log(h)
        return float(-ll.sum())

    best = None
    # 몇 개 출발점에서 L-BFGS-B → 가장 작은 음의 로그우도 (결정적)
    for al0, be0, nu0 in ((0.05, 0.90, 6.0), (0.10, 0.80, 8.0), (0.03, 0.95, 5.0), (0.15, 0.60, 4.0)):
        th0 = np.array([float(np.mean(x)), h0 * (1 - al0 - be0), al0, be0, nu0])
        res = optimize.minimize(
            nll,
            th0,
            method="L-BFGS-B",
            bounds=[(-1.0, 1.0), (1e-8, 10.0), (0.0, 1.0), (0.0, 1.0), (NU_LO, NU_HI)],
            options={"maxiter": 2000},
        )
        if best is None or res.fun < best.fun:
            best = res
    assert best is not None
    mu, om, al, be, nu = best.x
    return GarchT(
        mu=float(mu * s),
        omega=float(om * s * s),
        alpha=float(al),
        beta=float(be),
        nu=float(nu),
        loglik=float(-best.fun - r.size * np.log(s)),
        success=bool(best.success),
        message=str(best.message),
    )


def garch_filter(r: np.ndarray, g: GarchT) -> tuple[np.ndarray, np.ndarray]:
    """적합 모수로 (σ², z) 경로. σ²_0 = 무조건부 분산."""
    eps = np.asarray(r, float) - g.mu
    h = _garch_var(eps, g.omega, g.alpha, g.beta, g.uncond_var)
    return h, eps / np.sqrt(h)


# ── DCC / CCC 다변량 t ─────────────────────────────────────────────


def _mvt_logpdf(z: np.ndarray, R: np.ndarray, nu: float) -> float:
    """분산 1 정규화 다변량 t 의 log 밀도 (상관행렬 R)."""
    n = z.size
    L = np.linalg.cholesky(R)
    y = np.linalg.solve(L, z)
    quad = float(y @ y)
    logdet = 2.0 * float(np.log(np.diag(L)).sum())
    c = special.gammaln((nu + n) / 2) - special.gammaln(nu / 2) - n / 2 * np.log(np.pi * (nu - 2))
    return float(c - 0.5 * logdet - (nu + n) / 2 * np.log1p(quad / (nu - 2)))


def dcc_correlations(z: np.ndarray, a: float, b: float, qbar: np.ndarray) -> np.ndarray:
    """R_t (T, N, N). Q_0 = Q̄, Q_t = (1−a−b)Q̄ + a z_{t−1}z_{t−1}ᵀ + b Q_{t−1}."""
    T, N = z.shape
    out = np.empty((T, N, N))
    q = qbar.copy()
    for t in range(T):
        if t > 0:
            q = (1 - a - b) * qbar + a * np.outer(z[t - 1], z[t - 1]) + b * q
        d = 1.0 / np.sqrt(np.diag(q))
        out[t] = q * np.outer(d, d)
    return out


@dataclass(frozen=True)
class MultiT:
    kind: str  # "DCC" | "CCC"
    margins: tuple[GarchT, ...]
    qbar: np.ndarray
    a: float
    b: float
    nu: float
    loglik: float
    success: bool
    message: str
    tickers: tuple[str, ...] = field(default_factory=tuple)


def _qbar(z: np.ndarray) -> np.ndarray:
    q = z.T @ z / z.shape[0]
    d = 1.0 / np.sqrt(np.diag(q))
    return q * np.outer(d, d)


def fit_multit(returns: np.ndarray, kind: str, tickers: tuple[str, ...] = ()) -> MultiT:
    """returns (T, N). kind=DCC: (a, b, ν) 적합. kind=CCC: a=b=0 에서 ν 만 적합."""
    R = np.asarray(returns, float)
    margins = tuple(fit_garch_t(R[:, j]) for j in range(R.shape[1]))
    z = np.column_stack([garch_filter(R[:, j], margins[j])[1] for j in range(R.shape[1])])
    qbar = _qbar(z)

    def nll(th: np.ndarray) -> float:
        if kind == "DCC":
            a, b, nu = th
            if a + b >= PERSIST_MAX:
                return 1e10
            Rt = dcc_correlations(z, a, b, qbar)
            return -float(sum(_mvt_logpdf(z[t], Rt[t], nu) for t in range(z.shape[0])))
        (nu,) = th
        return -float(sum(_mvt_logpdf(z[t], qbar, nu) for t in range(z.shape[0])))

    if kind == "DCC":
        best = None
        for a0, b0 in ((0.02, 0.95), (0.05, 0.90), (0.01, 0.97)):
            res = optimize.minimize(
                nll,
                np.array([a0, b0, 8.0]),
                method="L-BFGS-B",
                bounds=[(0.0, 1.0), (0.0, 1.0), (NU_LO, NU_HI)],
            )
            if best is None or res.fun < best.fun:
                best = res
        assert best is not None
        a, b, nu = (float(v) for v in best.x)
    elif kind == "CCC":
        best = optimize.minimize(nll, np.array([8.0]), method="L-BFGS-B", bounds=[(NU_LO, NU_HI)])
        a, b, nu = 0.0, 0.0, float(best.x[0])
    else:
        raise ValueError(kind)
    return MultiT(
        kind, margins, qbar, a, b, nu, float(-best.fun), bool(best.success), str(best.message), tickers
    )


def validity_numeric(m: MultiT) -> dict[str, bool]:
    """N1: 최적화 성공·정상성·자유도·경계 이격 (경계 근처면 식별 실패로 본다)."""
    out: dict[str, bool] = {}
    for j, g in enumerate(m.margins):
        out[f"margin{j}_success"] = g.success
        out[f"margin{j}_stationary"] = g.alpha >= 0 and g.beta >= 0 and g.persistence < PERSIST_MAX
        out[f"margin{j}_nu_range"] = NU_LO + BOUND_TOL < g.nu < NU_HI - BOUND_TOL
        out[f"margin{j}_interior"] = (
            g.alpha > BOUND_TOL and g.beta > BOUND_TOL and g.persistence < PERSIST_MAX - BOUND_TOL
        )
    out["joint_success"] = m.success
    out["joint_nu_range"] = NU_LO + BOUND_TOL < m.nu < NU_HI - BOUND_TOL
    if m.kind == "DCC":
        out["dcc_stationary"] = m.a >= 0 and m.b >= 0 and m.a + m.b < PERSIST_MAX
        out["dcc_interior"] = m.a > BOUND_TOL and m.b > BOUND_TOL and m.a + m.b < PERSIST_MAX - BOUND_TOL
    out["qbar_pd"] = bool(np.linalg.eigvalsh(m.qbar).min() > 0)
    return out


# ── 모의 ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Shock:
    """대립·음성 대조 시나리오의 조작 (계약 §9). 위치는 burn-in 이후 0-기반 일 index."""

    var_mult: np.ndarray | None = None  # (T, N) 분산 배율 (sd 는 √배) — 주변 분산 변화
    corr_override: np.ndarray | None = None  # (N, N) 상관행렬 — [corr_start, corr_end) 동안 R_t 대체
    corr_start: int = -1
    corr_end: int = -1
    z_override: dict[int, np.ndarray] | None = None  # 날짜 → 표준화 혁신 고정 (공통 충격)


def simulate(
    m: MultiT, n: int, rng: np.random.Generator, burn: int = 500, shock: Shock | None = None
) -> tuple[np.ndarray, float]:
    """(T, N) 수익률과 경로 전체(burn-in 포함) R_t 의 최소 고유값. 혁신 z = √((ν−2)/ν)·L x / √(W/ν), x~N(0,I), W~χ²_ν."""
    N = len(m.margins)
    total = burn + n
    x = rng.standard_normal((total, N))
    W = rng.chisquare(m.nu, size=total)
    scale = np.sqrt((m.nu - 2) / m.nu) / np.sqrt(W / m.nu)
    mu = np.array([g.mu for g in m.margins])
    om = np.array([g.omega for g in m.margins])
    al = np.array([g.alpha for g in m.margins])
    be = np.array([g.beta for g in m.margins])
    h = np.array([g.uncond_var for g in m.margins])
    q = m.qbar.copy()
    zprev = np.zeros(N)
    eps_prev = np.zeros(N)
    out = np.empty((n, N))
    min_eig = np.inf
    for t in range(total):
        if t > 0:
            h = om + al * eps_prev**2 + be * h
            if m.kind == "DCC":
                q = (1 - m.a - m.b) * m.qbar + m.a * np.outer(zprev, zprev) + m.b * q
        d = 1.0 / np.sqrt(np.diag(q))
        Rt = q * np.outer(d, d)
        k = t - burn
        if shock is not None and shock.corr_override is not None and shock.corr_start <= k < shock.corr_end:
            Rt = shock.corr_override
        L = np.linalg.cholesky(Rt)  # 양정치가 아니면 여기서 LinAlgError
        min_eig = min(min_eig, float(np.linalg.eigvalsh(Rt)[0]))
        z = scale[t] * (L @ x[t])
        if shock is not None and shock.z_override is not None and k in shock.z_override:
            z = shock.z_override[k].copy()
        eps = np.sqrt(h) * z
        if k >= 0:
            mult = 1.0 if shock is None or shock.var_mult is None else shock.var_mult[k]
            out[k] = mu + eps * np.sqrt(mult)
        zprev, eps_prev = z, eps
    return out, min_eig


def nearest_correlation(A: np.ndarray, eig_floor: float = 1e-6) -> np.ndarray:
    """대칭화 → 음의 고유값 절단 → 대각 1 로 재정규화 (V6 상관 행렬용)."""
    S = (A + A.T) / 2
    w, V = np.linalg.eigh(S)
    B = (V * np.maximum(w, eig_floor)) @ V.T
    d = 1.0 / np.sqrt(np.diag(B))
    return B * np.outer(d, d)
