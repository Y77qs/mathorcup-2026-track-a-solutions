#!/usr/bin/env python
"""q2_att2_network.py — the ATTACHMENT-2 descriptive chemistry correlation network for Q2 (v6 §5).

WHAT THIS IS.  2.csv (data/raw/imported/*-2.csv) ships with the attachment as a 231 x 231 correlation
matrix over the 231 chemistry features.  This script turns that table into the entity the v6 task list
asks for: a node table, an edge table, the threshold rule, the positive/negative edge split, the connected
component statistics and a figure.  Rule (pre-declared, v6 §5): an UNDIRECTED edge {i, j}, i < j, whenever
|rho_ij| >= 0.5, with no self-loops (i < j removes them by construction) and the sign of rho_ij kept.

WHAT THIS IS NOT.  This is NOT the graph used by the independent prediction step.  The graph-regularised
low-rank model rebuilds its |W| graph at tau = 0.5 INSIDE every training replication
(q2_fix.bootstrap -> pointscores -> q1_lib.build_graph), so no whole-sample structure reaches the
validation.  The delivered predictive numbers therefore do not use this table; it is read here only for
the descriptive network / factor-interpretation part of Q2, and it is same-source with the attachment.

EXPECTED VALUES ARE CHECKED, NOT FORCED.  With the rule above the matrix gives 231 nodes, 645 edges and
52 connected components (largest 175).  The script recomputes them, writes the measured values, compares
with the expected ones, and reports any difference together with its reason; it never edits the rule to
make a number match.

Run (local; writes into outputs/q2/attachment2_network by default):
    python src/q2_att2_network.py
    python src/q2_att2_network.py --export-dir outputs/q2/attachment2_network
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

SRC = Path(__file__).resolve().parent
PROJECT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from target_columns import FEATURE_COLS  # noqa: E402  (pure constants, no contract import)

#: pre-declared rule (v6 §5): undirected, no self-loops, |rho| >= 0.5
THRESHOLD = 0.5
COMPARATOR = ">="
UNDIRECTED = True
SELF_LOOPS = False
#: measured on the real attachment table; checked, never used to tune the rule
EXPECTED = {"nodes": 231, "edges": 645, "components": 52, "largestComponent": 175}
CORR_GLOB = "data/raw/imported/*-2.csv"
CHEM_META = "data/clean/q2_chem_meta.json"
OUT_DIR_DEFAULT = "outputs/q2/attachment2_network"


# ---------------------------------------------------------------------------------------------------- io
def sha256_file(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalise(text: str) -> str:
    """Same normalisation as q2_lib.normalise_label (lower case, alphanumerics only)."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


# ---------------------------------------------------------------------------------------------------- data
def locate_corr_table(project: Path) -> Path:
    matches = sorted(project.glob(CORR_GLOB))
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one {CORR_GLOB} in {project}, found {[str(m) for m in matches]}")
    return matches[0]


def load_aligned_matrix(project: Path) -> dict:
    """Read 2.csv and align it to target_columns.FEATURE_COLS through q2_chem_meta.json corrIndex."""
    table_path = locate_corr_table(project)
    raw = pd.read_csv(table_path, index_col=0)
    meta = json.loads((project / CHEM_META).read_text(encoding="utf-8"))
    records = sorted(meta["features"], key=lambda record: int(record["corrIndex"]))
    indices = [int(record["corrIndex"]) for record in records]
    labels = [str(record["corrLabel"]) for record in records]
    names = [str(record["name"]) for record in records]
    if indices != list(range(len(records))):
        raise SystemExit(f"{CHEM_META} corrIndex is not a 0..{len(records) - 1} permutation")
    if names != list(FEATURE_COLS):
        raise SystemExit("q2_chem_meta.json names (by corrIndex) disagree with target_columns.FEATURE_COLS")
    if raw.shape != (len(records), len(records)):
        raise SystemExit(f"{table_path.name} has shape {raw.shape}, expected {len(records)} square")

    row_labels = [str(value) for value in raw.index]
    col_labels = [str(value) for value in raw.columns]
    exact_rows = sum(1 for left, right in zip(row_labels, labels) if left == right)
    exact_cols = sum(1 for left, right in zip(col_labels, labels) if left == right)
    alignment = {
        "rule": "position (corrIndex) is used ONLY after it is verified by the corrLabel text on both axes",
        "exactRowLabelMatches": int(exact_rows), "exactColumnLabelMatches": int(exact_cols),
        "n": len(records), "positionalUsed": bool(exact_rows == len(records) and exact_cols == len(records)),
    }
    if not alignment["positionalUsed"]:
        # fall back to a name join, refusing ambiguity instead of guessing a position
        by_label: dict = {}
        for position, label in enumerate(labels):
            by_label.setdefault(normalise(label), []).append(position)
        ambiguous = {key: value for key, value in by_label.items() if len(value) > 1}
        row_pos = {}
        for position, label in enumerate(row_labels):
            key = normalise(label)
            if key not in by_label:
                raise SystemExit(f"2.csv row {label!r} matches no q2_chem_meta corrLabel")
            if len(by_label[key]) > 1:
                raise SystemExit(f"2.csv row {label!r} is ambiguous: {ambiguous.get(key)}")
            row_pos[position] = by_label[key][0]
        if len(set(row_pos.values())) != len(row_pos):
            raise SystemExit("2.csv rows map to the same feature twice after normalisation")
        matrix = np.empty((len(records), len(records)), dtype=float)
        values = raw.to_numpy(dtype=float)
        for source_row, target_row in row_pos.items():
            matrix[target_row, :] = values[source_row, :]
        alignment["nameJoinUsed"] = True
        alignment["ambiguousNormalisedLabels"] = {key: value for key, value in ambiguous.items()}
        alignment["note"] = "2.csv labels matched to corrLabel by normalised text, NOT by position"
    else:
        matrix = raw.to_numpy(dtype=float)
        alignment["nameJoinUsed"] = False

    if not np.isfinite(matrix).all():
        raise SystemExit("2.csv contains non-finite correlations")
    if float(np.abs(matrix - matrix.T).max()) > 1e-9:
        raise SystemExit("2.csv is not symmetric: an undirected network would need two different weights")
    if float(np.abs(np.diag(matrix) - 1.0).max()) > 1e-9:
        raise SystemExit("2.csv diagonal is not 1: the table is not a correlation matrix")
    return {"path": table_path, "matrix": matrix, "names": names, "labels": labels,
            "kinds": [str(record["kind"]) for record in records], "alignment": alignment,
            "metaSha256": sha256_file(project / CHEM_META)}


# ---------------------------------------------------------------------------------------------------- graph
def build_graph(matrix: np.ndarray) -> dict:
    """Undirected edges with |rho| >= THRESHOLD, i < j (so no self-loop can survive)."""
    n = matrix.shape[0]
    upper = np.triu_indices(n, 1)
    abs_values = np.abs(matrix[upper])
    mask = abs_values >= THRESHOLD
    source = upper[0][mask].astype(int)
    target = upper[1][mask].astype(int)
    rho = matrix[upper][mask].astype(float)
    order = np.lexsort((target, source))
    source, target, rho = source[order], target[order], rho[order]

    adjacency = np.zeros((n, n), dtype=np.int8)
    adjacency[source, target] = 1
    adjacency[target, source] = 1
    count, labels = connected_components(csr_matrix(adjacency), directed=False)
    sizes = np.bincount(labels)
    # deterministic, readable module ids: largest component first, then by smallest feature position
    order_modules = sorted(range(int(count)), key=lambda module: (-int(sizes[module]),
                                                                  int(np.nonzero(labels == module)[0][0])))
    relabel = {old: new for new, old in enumerate(order_modules)}
    module_of = np.asarray([relabel[int(value)] for value in labels], dtype=int)
    module_sizes = np.bincount(module_of)
    degree = adjacency.sum(axis=1).astype(int)
    if int(degree.sum()) != 2 * int(source.size):
        raise SystemExit("degree sum disagrees with the edge count: the adjacency is not symmetric")
    return {"source": source, "target": target, "rho": rho, "moduleOf": module_of,
            "moduleSizes": module_sizes, "degree": degree, "nComponents": int(count),
            "components": labels}


def component_order(module_of: np.ndarray, module_sizes: np.ndarray) -> list:
    return list(range(len(module_sizes)))


# ---------------------------------------------------------------------------------------------------- layout
def _fruchterman_reingold(nodes: list, edges: list, iterations: int = 220, size: float = 1.0) -> dict:
    """Deterministic Fruchterman-Reingold layout: circular start, no RNG, fixed sweep count."""
    n = len(nodes)
    if n == 1:
        return {nodes[0]: np.zeros(2, dtype=float)}
    local = {node: index for index, node in enumerate(nodes)}
    angles = 2.0 * math.pi * np.arange(n) / float(n)
    position = np.column_stack([0.4 * size * np.cos(angles), 0.4 * size * np.sin(angles)])
    k = size / math.sqrt(float(n))
    temperature = 0.10 * size
    links = [(local[a], local[b], float(w)) for a, b, w in edges if a in local and b in local]
    for _ in range(int(iterations)):
        delta = position[:, None, :] - position[None, :, :]
        distance = np.sqrt((delta ** 2).sum(axis=2))
        np.fill_diagonal(distance, np.inf)
        unit = delta / np.maximum(distance, 1e-9)[:, :, None]
        displacement = (k * k / np.maximum(distance, 1e-9))[:, :, None] * unit
        displacement = displacement.sum(axis=1)
        for left, right, weight in links:
            vector = position[left] - position[right]
            length = max(float(np.linalg.norm(vector)), 1e-9)
            step = weight * (length * length / k) * vector / length
            displacement[left] -= step
            displacement[right] += step
        magnitude = np.linalg.norm(displacement, axis=1)
        scale = np.minimum(magnitude, temperature) / np.maximum(magnitude, 1e-9)
        position = position + displacement * scale[:, None]
        position = np.clip(position, -size, size)
        temperature = max(temperature * 0.97, 1e-3 * size)
    position = position - position.mean(axis=0)
    span = max(float(np.abs(position).max()), 1e-9)
    return {node: position[local[node]] / span * size for node in nodes}


def _component_edges(graph: dict, module: int) -> list:
    mask = (graph["moduleOf"][graph["source"]] == module) & (graph["moduleOf"][graph["target"]] == module)
    return [(int(a), int(b), abs(float(w))) for a, b, w in zip(graph["source"][mask],
                                                               graph["target"][mask],
                                                               graph["rho"][mask])]


def layout(graph: dict, names: list) -> dict:
    """Deterministic layout: largest component in the middle, every other component on an outer ring.

    No RNG anywhere (circular starts + a fixed Fruchterman-Reingold sweep count), so the figure and the
    coordinates written to nodes.csv are reproducible byte for byte.
    """
    module_of = graph["moduleOf"]
    sizes = graph["moduleSizes"]
    n = len(names)
    coordinates = np.zeros((n, 2), dtype=float)
    placement = np.array(["largest"] * n, dtype=object)
    giant = int(np.argmax(sizes))
    giant_nodes = [int(value) for value in np.nonzero(module_of == giant)[0]]
    positions = _fruchterman_reingold(giant_nodes, _component_edges(graph, giant), size=1.0)
    for node in giant_nodes:
        coordinates[node] = positions[node]

    small = [module for module in range(len(sizes)) if module != giant]
    small.sort(key=lambda module: (-int(sizes[module]), int(np.nonzero(module_of == module)[0][0])))
    multi = [module for module in small if sizes[module] > 1]
    singles = [module for module in small if sizes[module] == 1]
    # multi-node components just outside the giant, singles on a slightly tighter ring, both evenly spaced
    for index, module in enumerate(multi):
        angle = 2.0 * math.pi * (index + 0.5) / max(len(multi), 1) + math.pi / 3.0
        centre = np.array([1.55 * math.cos(angle), 1.55 * math.sin(angle)])
        members = [int(value) for value in np.nonzero(module_of == module)[0]]
        positions = _fruchterman_reingold(members, _component_edges(graph, module), size=0.14)
        for node in members:
            coordinates[node] = centre + positions[node]
            placement[node] = "small"
    for index, module in enumerate(singles):
        angle = 2.0 * math.pi * index / max(len(singles), 1) + math.pi / len(singles) * 0.5
        node = int(np.nonzero(module_of == module)[0][0])
        coordinates[node] = np.array([1.25 * math.cos(angle), 1.25 * math.sin(angle)])
        placement[node] = "isolated"
    return {"coordinates": coordinates, "placement": placement,
            "giant": giant,
            "plotBounds": {"xMin": float(coordinates[:, 0].min()), "xMax": float(coordinates[:, 0].max()),
                           "yMin": float(coordinates[:, 1].min()), "yMax": float(coordinates[:, 1].max())}}


# ---------------------------------------------------------------------------------------------------- outputs
def write_nodes(path: Path, graph: dict, payload: dict, layout_payload: dict) -> int:
    header = ["nodeId", "corrIndex", "feature", "corrLabel", "kind", "moduleId", "moduleSize", "degree",
              "placement", "x", "y"]
    coordinates = layout_payload["coordinates"]
    placement = layout_payload["placement"]
    rows = []
    for position, name in enumerate(payload["names"]):
        module = int(graph["moduleOf"][position])
        rows.append([position, position, name, payload["labels"][position], payload["kinds"][position],
                     module, int(graph["moduleSizes"][module]), int(graph["degree"][position]),
                     placement[position], f"{coordinates[position, 0]:.9f}", f"{coordinates[position, 1]:.9f}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        import csv
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def write_edges(path: Path, graph: dict, payload: dict) -> int:
    header = ["sourceIndex", "targetIndex", "sourceFeature", "targetFeature", "sourceLabel", "targetLabel",
              "rho", "absRho", "sign"]
    rows = []
    for left, right, value in zip(graph["source"], graph["target"], graph["rho"]):
        rows.append([int(left), int(right), payload["names"][left], payload["names"][right],
                     payload["labels"][left], payload["labels"][right], f"{float(value):.17g}",
                     f"{abs(float(value)):.17g}", "positive" if value > 0 else "negative"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        import csv
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def draw(path: Path, graph: dict, payload: dict, layout_payload: dict) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    coordinates = layout_payload["coordinates"]
    placement = layout_payload["placement"]
    positive = graph["rho"] > 0
    kind_style = {
        "single_compound": ("#4a5568", 12.0, "single compound (216)"),
        "element_or_index": ("#dd6b20", 60.0, "element / index (3)"),
        "physical_parameter": ("#2f855a", 30.0, "physical parameter (7)"),
        "derived_sum": ("#6b46c1", 44.0, "derived sum (5)"),
    }
    fig, axes = plt.subplots(figsize=(15.0, 14.4), dpi=170)
    axes.set_facecolor("white")
    for mask, color in ((positive, "#2b6cb0"), (~positive, "#c53030")):
        for left, right, value in zip(graph["source"][mask], graph["target"][mask], graph["rho"][mask]):
            axes.plot([coordinates[left, 0], coordinates[right, 0]],
                      [coordinates[left, 1], coordinates[right, 1]], color=color, alpha=0.32,
                      linewidth=0.35 + 1.6 * (abs(float(value)) - THRESHOLD), zorder=1)
    for kind, (color, base_size, _label) in kind_style.items():
        members = [position for position, value in enumerate(payload["kinds"]) if value == kind]
        if not members:
            continue
        sizes = [base_size * (0.6 + float(graph["degree"][position]) / 30.0) for position in members]
        axes.scatter(coordinates[members, 0], coordinates[members, 1], s=sizes, c=color,
                     edgecolors="white", linewidths=0.5, zorder=2)
    # label the hubs plus every non-single-compound feature, and everything on the outer ring that has a
    # partner; the bbox keeps the dense core readable without hiding the structure
    by_degree = [int(value) for value in np.argsort(-graph["degree"], kind="mergesort")]
    labelled = {position for position in by_degree if int(graph["degree"][position]) >= 14}
    labelled |= {position for position, kind in enumerate(payload["kinds"]) if kind != "single_compound"}
    labelled |= {position for position in range(len(payload["names"]))
                 if placement[position] == "small"}
    for position in sorted(labelled):
        x, y = coordinates[position]
        radius = math.hypot(x, y)
        if placement[position] == "largest":
            offset = (0.0, 5.0)
            horizontal, vertical = "center", "bottom"
        else:
            scale = 7.0 / max(radius, 1e-9)
            offset = (x * scale, y * scale)
            horizontal = "left" if x >= 0 else "right"
            vertical = "bottom" if y >= 0 else "top"
        axes.annotate(payload["names"][position], (x, y), fontsize=5.4, color="#1a202c",
                      ha=horizontal, va=vertical, zorder=3, xytext=offset, textcoords="offset points",
                      bbox=dict(boxstyle="round,pad=0.10", facecolor="white", edgecolor="none", alpha=0.70))
    handles = [Line2D([0], [0], color="#2b6cb0", linewidth=1.4,
                      label=f"positive edge ({int(positive.sum())})"),
               Line2D([0], [0], color="#c53030", linewidth=1.4,
                      label=f"negative edge ({int((~positive).sum())})")]
    handles += [Line2D([0], [0], color=color, marker="o", linestyle="", label=label)
                for color, _size, label in kind_style.values()]
    legend = fig.legend(handles=handles, loc="lower center", ncol=7, fontsize=8.5, frameon=True,
                        bbox_to_anchor=(0.5, 0.012))
    axes.text(0.0, 1.34, f"largest component: {int(graph['moduleSizes'].max())} nodes",
              ha="center", va="bottom", fontsize=9.5, color="#2d3748")
    axes.text(0.0, -1.34, "outer ring: 51 other components\n(3 + 3 + 2 nodes, 48 isolated features)",
              ha="center", va="top", fontsize=8.0, color="#4a5568")
    axes.set_title(
        f"Attachment-2 chemistry correlation network (undirected, |rho| >= {THRESHOLD}, no self-loops)\n"
        f"{len(payload['names'])} nodes, {int(graph['source'].size)} edges, "
        f"{int(graph['nComponents'])} connected components (largest {int(graph['moduleSizes'].max())})",
        fontsize=12)
    axes.text(0.5, -0.045,
              "Node size = degree; node colour = feature kind. Descriptive full-sample table: used for the Q2 "
              "network / factor interpretation only.\n"
              "The predictive training graph is rebuilt inside every training fold, so this table never enters "
              "the validation.",
              transform=axes.transAxes, ha="center", va="top", fontsize=8.2, color="#4a5568")
    axes.set_aspect("equal")
    axes.axis("off")
    fig.tight_layout(rect=(0, 0.075, 1, 0.93))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def markdown_report(path: Path, graph: dict, payload: dict, comparison: dict, stats: dict) -> int:
    lines = ["# 附件2 描述性化学相关网络（Q2 网络/因素解释）", ""]
    lines.append("规则（预先声明，v6 §5）：无向边 `{i, j}`，`i < j`（因此不可能有自环），当且仅当 "
                 f"`|rho_ij| {COMPARATOR} {THRESHOLD}`；保留 `rho_ij` 的符号。")
    lines.append("")
    lines.append(f"- 输入：`{stats['inputPath']}`（sha256 `{stats['inputSha256']}`）")
    lines.append(f"- 对齐：{payload['alignment']['rule']}；精确 corrLabel 匹配 "
                 f"{payload['alignment']['exactRowLabelMatches']}/{payload['alignment']['n']} 行、"
                 f"{payload['alignment']['exactColumnLabelMatches']}/{payload['alignment']['n']} 列；"
                 f"按名加入={'是' if payload['alignment'].get('nameJoinUsed') else '否'}")
    lines.append("")
    lines.append("| 指标 | 实测 | 预期 | 一致 |")
    lines.append("|---|---|---|---|")
    for key, label in (("nodes", "节点数"), ("edges", "边数"), ("components", "连通分量数"),
                       ("largestComponent", "最大分量规模")):
        actual = comparison["actual"][key]
        expected = comparison["expected"][key]
        lines.append(f"| {label} | {actual} | {expected} | {'是' if actual == expected else '**否**'} |")
    lines.append("")
    lines.append(f"- 正边 {stats['positiveEdges']} 条，负边 {stats['negativeEdges']} 条（"
                 f"负边占 {100.0 * stats['negativeEdges'] / max(stats['edges'], 1):.1f}%）")
    lines.append(f"- |rho| 在边上：最小 {stats['absRhoMin']:.4f}，中位 {stats['absRhoMedian']:.4f}，"
                 f"最大 {stats['absRhoMax']:.4f}")
    lines.append(f"- 度：中位 {stats['degreeMedian']}，最大 {stats['degreeMax']}，孤立节点 "
                 f"{stats['isolatedNodes']} 个")
    lines.append(f"- 分量规模（降序）：{comparison['sizesDescending']}")
    lines.append("")
    lines.append("## 最大分量内度最高的 10 个节点")
    lines.append("")
    lines.append("| # | feature | corrLabel | kind | degree | moduleId |")
    lines.append("|---|---|---|---|---|---|")
    for rank, row in enumerate(stats["topHubs"], start=1):
        lines.append(f"| {rank} | {row['feature']} | {row['corrLabel']} | {row['kind']} | {row['degree']} | "
                     f"{row['moduleId']} |")
    lines.append("")
    lines.append("## 用途与边界")
    lines.append("")
    lines.append("- 该网络是**描述性**的：它来自附件随附的 231×231 相关矩阵（与附件同源），用来说明 Q2 的化学"
                 "模块结构与正负相关格局，不参与任何 Top-3 选择，也不是独立外部验证。")
    lines.append("- **独立预测的训练图仍在训练折内构建**：`q2_fix.py` 的每次 bootstrap 重采样都会重新计算 "
                 "`tau = 0.5` 的训练内 Spearman 图（`q1_lib.build_graph`），全样本矩阵不会进入验证，避免把"
                 "全样本结构泄漏到预测评价里。")
    lines.append("- 连通分量只是 `|rho| >= 0.5` 的阈值图结构，不代表因果关系；阈值本身是预先声明的规则，"
                 "不是调参结果。")
    if not comparison["matchesExpected"]:
        lines.append("")
        lines.append(f"**注意**：本次实测与预期不一致 —— {comparison['differences']}。差异已如实记录，"
                     "规则没有被改动来凑数。")
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return len(lines)


# ---------------------------------------------------------------------------------------------------- main
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Attachment-2 descriptive correlation network for Q2")
    parser.add_argument("--export-dir", default=OUT_DIR_DEFAULT,
                        help=f"output directory (default {OUT_DIR_DEFAULT})")
    args = parser.parse_args(argv)
    out_dir = Path(args.export_dir)
    if not out_dir.is_absolute():
        out_dir = PROJECT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = load_aligned_matrix(PROJECT)
    graph = build_graph(payload["matrix"])
    layout_payload = layout(graph, payload["names"])
    nodes = write_nodes(out_dir / "nodes.csv", graph, payload, layout_payload)
    edges = write_edges(out_dir / "edges.csv", graph, payload)

    sizes = np.bincount(graph["moduleOf"])
    sizes_desc = sorted((int(value) for value in sizes), reverse=True)
    positive = graph["rho"] > 0
    module_hist = {}
    for module, size in enumerate(sizes):
        module_hist.setdefault(int(size), 0)
        module_hist[int(size)] += 1
    actual = {"nodes": int(len(payload["names"])), "edges": int(graph["source"].size),
              "components": int(graph["nComponents"]), "largestComponent": int(sizes.max()),
              "positiveEdges": int(positive.sum()), "negativeEdges": int((~positive).sum()),
              "isolatedNodes": int((graph["degree"] == 0).sum())}
    differences = {key: {"actual": actual[key], "expected": EXPECTED[key]}
                   for key in EXPECTED if actual[key] != EXPECTED[key]}
    comparison = {"expected": EXPECTED, "actual": actual, "differences": differences,
                  "matchesExpected": not differences, "sizesDescending": sizes_desc}
    top_hubs = []
    for position in np.argsort(-graph["degree"], kind="mergesort")[:10]:
        position = int(position)
        module = int(graph["moduleOf"][position])
        top_hubs.append({"feature": payload["names"][position], "corrLabel": payload["labels"][position],
                         "kind": payload["kinds"][position], "degree": int(graph["degree"][position]),
                         "moduleId": module})
    stats = {
        "inputPath": str(payload["path"].relative_to(PROJECT)),
        "inputSha256": sha256_file(payload["path"]),
        "metaSha256": payload["metaSha256"],
        "nodes": actual["nodes"], "edges": actual["edges"], "positiveEdges": actual["positiveEdges"],
        "negativeEdges": actual["negativeEdges"],
        "absRhoMin": float(np.abs(graph["rho"]).min()), "absRhoMax": float(np.abs(graph["rho"]).max()),
        "absRhoMedian": float(np.median(np.abs(graph["rho"]))),
        "degreeMedian": int(np.median(graph["degree"])), "degreeMax": int(graph["degree"].max()),
        "isolatedNodes": actual["isolatedNodes"], "componentSizeHistogram": module_hist,
        "topHubs": top_hubs,
    }

    rules = {
        "source": "pre-declared rule from MathorCup_A_v6_面向复赛修改说明.md §5",
        "threshold": THRESHOLD, "comparator": COMPARATOR, "undirected": UNDIRECTED,
        "selfLoops": SELF_LOOPS, "edgeRule": "edge {i, j} for i < j iff |rho_ij| >= threshold",
        "signRule": "sign of rho_ij is kept on the edge; the graph is undirected in topology, signed in value",
        "nodeRule": "all 231 chemistry features of data/clean/q2_chem_meta.json, in corrIndex order",
        "thresholdSource": "fixed by the v6 task list before looking at the measured counts; not tuned",
        "inputs": {stats["inputPath"]: stats["inputSha256"], CHEM_META: stats["metaSha256"]},
        "alignment": payload["alignment"],
        "measured": actual, "expected": EXPECTED, "matchesExpected": comparison["matchesExpected"],
        "scope": "descriptive, same-source with the attachment: Q2 network/factor interpretation only. The "
                 "predictive training graph is rebuilt inside every training resample at tau = 0.5 "
                 "(q2_fix.py -> q1_lib.build_graph); this full-sample table never enters the validation.",
    }
    write_json(out_dir / "rules.json", rules)
    write_json(out_dir / "component_summary.json", {
        "nComponents": actual["components"],
        "largestComponentSize": actual["largestComponent"],
        "largestComponentShare": float(actual["largestComponent"]) / float(actual["nodes"]),
        "componentSizesDescending": sizes_desc,
        "componentSizeHistogram": {str(key): value for key, value in sorted(module_hist.items(),
                                                                           reverse=True)},
        "isolatedNodes": actual["isolatedNodes"],
        "positiveEdges": actual["positiveEdges"], "negativeEdges": actual["negativeEdges"],
        "edgeCount": actual["edges"], "nodeCount": actual["nodes"],
        "expected": EXPECTED, "actual": {key: actual[key] for key in EXPECTED},
        "matchesExpected": comparison["matchesExpected"], "differences": differences,
        "definition": "connected components of the undirected |rho| >= 0.5 threshold graph; singleton "
                      "components (degree 0 features) are counted as components of size 1",
        "note": "counts are measured on the real attachment table and compared with the expected values; a "
                "difference would be reported here and in stats.md, never repaired by editing the rule",
    })
    markdown_report(out_dir / "stats.md", graph, payload, comparison, stats)
    draw(out_dir / "network.png", graph, payload, layout_payload)

    report = {"exportDir": str(out_dir), "nodes": nodes, "edges": edges,
              "nComponents": actual["components"], "largestComponent": actual["largestComponent"],
              "positiveEdges": actual["positiveEdges"], "negativeEdges": actual["negativeEdges"],
              "matchesExpected": comparison["matchesExpected"], "differences": differences,
              "files": {}}
    for name in ("nodes.csv", "edges.csv", "rules.json", "component_summary.json", "stats.md",
                 "network.png"):
        path = out_dir / name
        report["files"][name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    if differences:
        print("WARNING: measured values differ from the expected ones: "
              + json.dumps(differences, ensure_ascii=False), flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
