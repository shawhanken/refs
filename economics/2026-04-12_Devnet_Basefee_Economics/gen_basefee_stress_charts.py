#!/usr/bin/env python3
"""
Simulated cycle basefee under sustained high load (illustrative only).
Uses the same integer update shape as node/execution/src/basefee.rs::update_one.

Narrative: over **180 blocks** (≈180s at 1s/block), **load alternates high/low** on a
square wave (same timing; low-phase ``used`` scaled below each scenario's T_c).
*past*: undersized T_c → high phases often hit the per-block cap (harsh swings).
*present*: T_c aligned with capacity → smaller amplitude for comparable stress ("better").

Y-axis: index where initial basefee = 100.
No third-party deps; writes SVG files.
"""
from __future__ import annotations


def update_one(
    basefee: int,
    used: int,
    target: int,
    alpha: int,
    denom: int,
    min_bf: int,
    max_bf: int,
) -> int:
    if target == 0:
        return basefee
    max_delta = basefee // denom
    if used > target:
        num = basefee * (used - target)
        delta = min(num // target // alpha, max_delta)
        new_bf = basefee + delta
    elif used < target:
        num = basefee * (target - used)
        delta = min(num // target // alpha, max_delta)
        new_bf = basefee - delta
    else:
        new_bf = basefee
    return max(min(new_bf, max_bf), min_bf)


def simulate(
    blocks: int,
    initial: int,
    used_per_block: int,
    target: int,
    alpha: int,
    denom: int,
    min_bf: int,
    max_bf: int,
) -> list[int]:
    out = [initial]
    bf = initial
    for _ in range(blocks):
        bf = update_one(bf, used_per_block, target, alpha, denom, min_bf, max_bf)
        out.append(bf)
    return out


def square_wave_used(
    blocks: int,
    used_high: int,
    used_low: int,
    high_run: int,
    low_run: int,
) -> list[int]:
    """Alternating high/low load per block (length == blocks)."""
    period = high_run + low_run
    out: list[int] = []
    for i in range(blocks):
        phase = i % period
        out.append(used_high if phase < high_run else used_low)
    return out


def simulate_variable(
    blocks: int,
    initial: int,
    used_each_block: list[int],
    target: int,
    alpha: int,
    denom: int,
    min_bf: int,
    max_bf: int,
) -> list[int]:
    assert len(used_each_block) == blocks
    out = [initial]
    bf = initial
    for u in used_each_block:
        bf = update_one(bf, u, target, alpha, denom, min_bf, max_bf)
        out.append(bf)
    return out


def to_index_100(series: list[int]) -> list[float]:
    b0 = series[0]
    return [100.0 * x / b0 for x in series]


def to_svg(
    series_y: list[float],
    title_zh: str,
    title_en: str,
    subtitle: str,
    out_path: str,
    line_color: str,
    footnote: str,
    y_label: str = "相对初始 cycle basefee（初值=100）",
) -> None:
    w, h = 900, 460
    pad_l, pad_r, pad_t, pad_b = 78, 28, 72, 88
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    ymin_f = min(series_y)
    ymax_f = max(series_y)
    if ymax_f == ymin_f:
        ymax_f = ymin_f + 1.0
    span = ymax_f - ymin_f
    margin = max(span * 0.06, 2.0)
    ymin_f -= margin
    ymax_f += margin

    n = len(series_y)
    xs = [pad_l + i * plot_w / (n - 1) for i in range(n)]

    def ty(v: float) -> float:
        return pad_t + plot_h * (1 - (v - ymin_f) / (ymax_f - ymin_f))

    ys = [ty(v) for v in series_y]
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in zip(xs, ys))

    grid_lines = []
    for i in range(5):
        gy = pad_t + i * plot_h / 4
        grid_lines.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w - pad_r}" y2="{gy:.1f}" stroke="#e8e8e8" stroke-width="1"/>'
        )

    y_ticks = []
    for i in range(5):
        gv = ymin_f + (ymax_f - ymin_f) * (4 - i) / 4
        gy = pad_t + i * plot_h / 4
        y_ticks.append(
            f'<text x="{pad_l - 8}" y="{gy + 4}" text-anchor="end" font-size="11" fill="#555" font-family="system-ui,sans-serif">{gv:.0f}</text>'
        )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <rect width="100%" height="100%" fill="#fafafa"/>
  <text x="{w/2}" y="28" text-anchor="middle" font-size="15" font-weight="600" fill="#111" font-family="system-ui,sans-serif">{title_zh}</text>
  <text x="{w/2}" y="48" text-anchor="middle" font-size="12" fill="#444" font-family="system-ui,sans-serif">{title_en}</text>
  <text x="{w/2}" y="68" text-anchor="middle" font-size="11" fill="#555" font-family="system-ui,sans-serif">{subtitle}</text>
  {chr(10).join(grid_lines)}
  <polyline fill="none" stroke="{line_color}" stroke-width="2.6" points="{pts}"/>
  <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#333" stroke-width="1"/>
  {chr(10).join(y_ticks)}
  <text x="{w/2}" y="{h - 58}" text-anchor="middle" font-size="12" fill="#333" font-family="system-ui,sans-serif">区块序号 / Block index（180 块 ≈ 180s，负载高低交替）</text>
  <text x="16" y="{pad_t + plot_h/2}" text-anchor="middle" font-size="11" fill="#555" font-family="system-ui,sans-serif" transform="rotate(-90 16 {pad_t + plot_h/2})">{y_label}</text>
  <text x="{w/2}" y="{h - 32}" text-anchor="middle" font-size="10" fill="#666" font-family="system-ui,sans-serif">{footnote}</text>
  <text x="{w/2}" y="{h - 14}" text-anchor="middle" font-size="10" fill="#888" font-family="system-ui,sans-serif">示意模拟 · 非链上实测数据</text>
</svg>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)


def main() -> None:
    alpha, denom = 8, 8
    max_bf = 10**30
    blocks = 180
    # 两图共用同一绝对负载序列：高相位打满、低相位明显低于目标，便于 basefee 随负载起伏
    used_high = 20_000_000
    # 低相位须低于各自 T_c，才能触发 basefee 回落；数值按目标成比例，避免右图跌穿地板至指数≈0
    used_low_past = 3_000_000
    used_low_present = 10_000_000
    # 高相位短、低相位长：便于在 180 块内反复起伏且纵轴可读
    high_run, low_run = 8, 22
    used_series_past = square_wave_used(
        blocks, used_high, used_low_past, high_run, low_run
    )
    used_series_present = square_wave_used(
        blocks, used_high, used_low_present, high_run, low_run
    )

    # 旧：T_c 小 → 高相位大幅超目标、常触顶 +12.5%；低相位回落仍难抵消 → 峰值高、波动大
    past_raw = simulate_variable(
        blocks=blocks,
        initial=1_000_000_000,
        used_each_block=used_series_past,
        target=5_000_000,
        alpha=alpha,
        denom=denom,
        min_bf=1,
        max_bf=max_bf,
    )
    past_idx = to_index_100(past_raw)
    to_svg(
        past_idx,
        title_zh="旧参数（示意）：负载高低交替时 basefee 大起大落",
        title_en="Legacy-style params: oscillating load → large basefee swings",
        subtitle=f"共 {blocks} 块（≈180s）：周期 {high_run + low_run} 块 — 高 {high_run} 块 used={used_high//1_000_000}M、低 {low_run} 块 used={used_low_past//1_000_000}M；T_c=5M（ALPHA=DENOM=8）",
        out_path="/home/ubuntu/workspace/refs/202604/20260412_basefee_stress_past_simulated.svg",
        line_color="#c0392b",
        footnote="高负载段相对目标偏差过大，费用对压力过于敏感，用户体验差。",
    )

    # 新：T_c 与容量对齐 → 同等负载波形下，超目标幅度收敛，波动更温和
    present_raw = simulate_variable(
        blocks=blocks,
        initial=100_000_000,
        used_each_block=used_series_present,
        target=12_500_000,
        alpha=alpha,
        denom=denom,
        min_bf=1,
        max_bf=max_bf,
    )
    present_idx = to_index_100(present_raw)
    to_svg(
        present_idx,
        title_zh="当前参数（示意）：同等负载波动 → basefee 更平滑",
        title_en="Current-style params: same load pattern → smoother basefee",
        subtitle=f"与左图相同的高负载相位；低相位 used={used_low_present//1_000_000}M（低于 T_c=12.5M）；T_c=12.5M（ALPHA=DENOM=8）",
        out_path="/home/ubuntu/workspace/refs/202604/20260412_basefee_stress_present_simulated.svg",
        line_color="#1e8449",
        footnote="目标与扩容一致：高峰仍上调、低谷仍回落，但振幅更可预期。",
    )

    print("Wrote:")
    print("  refs/202604/20260412_basefee_stress_past_simulated.svg")
    print("  refs/202604/20260412_basefee_stress_present_simulated.svg")
    print(f"Past index:   min={min(past_idx):.1f} max={max(past_idx):.1f} end={past_idx[-1]:.1f}")
    print(f"Present index:min={min(present_idx):.1f} max={max(present_idx):.1f} end={present_idx[-1]:.1f}")


if __name__ == "__main__":
    main()
