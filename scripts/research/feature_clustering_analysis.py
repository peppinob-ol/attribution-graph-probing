"""Dependency-light feature class naturalness analysis."""

from __future__ import annotations

import csv
import json
import math
import random
import struct
import zlib
from collections import Counter, defaultdict
from pathlib import Path


FEATURES = [
    "peak_consistency_main",
    "n_distinct_peaks_log1p",
    "func_vs_sem_pct",
    "conf_F",
    "sparsity_median",
    "layer",
]
RAW_FEATURES = [
    "peak_consistency_main",
    "n_distinct_peaks",
    "func_vs_sem_pct",
    "conf_F",
    "sparsity_median",
    "layer",
]
COLORS = [
    (31, 119, 180),
    (255, 127, 14),
    (44, 160, 44),
    (214, 39, 40),
    (148, 103, 189),
    (140, 86, 75),
]


def as_float(row, key):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return 0.0


def feature_class(row):
    if str(row.get("review", "")).lower() == "true":
        return "Ambiguous/Review"
    label = row.get("pred_label", "")
    subtype = row.get("subtype", "")
    if label == 'Say "X"':
        return 'Say "X"'
    if label == "Relationship":
        return "Relationship"
    if subtype == "Dictionary":
        return "Semantic (Dictionary)"
    if subtype == "Dictionary (fallback)":
        return "Semantic (Dictionary fallback)"
    return "Semantic (Concept)"


def load_rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in RAW_FEATURES:
            row[key] = as_float(row, key)
        row["n_distinct_peaks_log1p"] = math.log1p(row["n_distinct_peaks"])
        row["class"] = feature_class(row)
    return rows


def median(values):
    values = sorted(values)
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def mode(values):
    return Counter(values).most_common(1)[0][0]


def dedupe(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(int(row["layer"]), str(row["feature"]))].append(row)
    out = []
    for (layer, feature), group in grouped.items():
        row = {"dataset": mode([g["dataset"] for g in group]), "layer": layer, "feature": feature}
        for key in RAW_FEATURES:
            row[key] = median([g[key] for g in group])
        row["n_distinct_peaks_log1p"] = math.log1p(row["n_distinct_peaks"])
        row["class"] = mode([g["class"] for g in group])
        out.append(row)
    return out


def standardize(rows):
    matrix = [[row[key] for key in FEATURES] for row in rows]
    means = [sum(col) / len(col) for col in zip(*matrix)]
    stds = []
    for j, mean in enumerate(means):
        var = sum((row[j] - mean) ** 2 for row in matrix) / max(len(matrix) - 1, 1)
        stds.append(math.sqrt(var) or 1.0)
    return [[(row[j] - means[j]) / stds[j] for j in range(len(FEATURES))] for row in matrix]


def covariance(xs):
    n, d = len(xs), len(xs[0])
    return [[sum(x[i] * x[j] for x in xs) / max(n - 1, 1) for j in range(d)] for i in range(d)]


def matvec(mat, vec):
    return [sum(a * b for a, b in zip(row, vec)) for row in mat]


def norm(vec):
    return math.sqrt(sum(v * v for v in vec)) or 1.0


def first_two_pcs(xs):
    cov = covariance(xs)
    vecs = []
    for _ in range(2):
        vec = [1.0] + [0.0] * (len(cov) - 1)
        for _ in range(80):
            vec = matvec(cov, vec)
            n = norm(vec)
            vec = [v / n for v in vec]
        eig = sum(a * b for a, b in zip(vec, matvec(cov, vec)))
        vecs.append(vec)
        cov = [[cov[i][j] - eig * vec[i] * vec[j] for j in range(len(cov))] for i in range(len(cov))]
    return [[sum(x[j] * vec[j] for j in range(len(vec))) for vec in vecs] for x in xs]


def sqdist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def kmeans(xs, k, iters=35):
    centers = [xs[0]]
    while len(centers) < k:
        centers.append(max(xs, key=lambda x: min(sqdist(x, c) for c in centers)))
    labels = [0] * len(xs)
    for _ in range(iters):
        labels = [min(range(k), key=lambda c: sqdist(x, centers[c])) for x in xs]
        new_centers = []
        for c in range(k):
            members = [x for x, label in zip(xs, labels) if label == c]
            if not members:
                new_centers.append(centers[c])
                continue
            new_centers.append([sum(col) / len(members) for col in zip(*members)])
        if new_centers == centers:
            break
        centers = new_centers
    return labels, centers


def gmm_diag(xs, k, iters=25):
    labels, centers = kmeans(xs, k, iters=15)
    d = len(xs[0])
    weights = [1 / k] * k
    vars_ = [[1.0] * d for _ in range(k)]
    for _ in range(iters):
        resp = []
        for x in xs:
            logs = []
            for c in range(k):
                val = math.log(weights[c] + 1e-12)
                val -= 0.5 * sum(math.log(v + 1e-6) + (x[j] - centers[c][j]) ** 2 / (v + 1e-6) for j, v in enumerate(vars_[c]))
                logs.append(val)
            top = max(logs)
            probs = [math.exp(v - top) for v in logs]
            total = sum(probs) or 1.0
            resp.append([p / total for p in probs])
        nk = [sum(r[c] for r in resp) for c in range(k)]
        weights = [n / len(xs) for n in nk]
        centers = [[sum(r[c] * x[j] for r, x in zip(resp, xs)) / (nk[c] or 1.0) for j in range(d)] for c in range(k)]
        vars_ = [[max(sum(r[c] * (x[j] - centers[c][j]) ** 2 for r, x in zip(resp, xs)) / (nk[c] or 1.0), 1e-4) for j in range(d)] for c in range(k)]
    return [max(range(k), key=lambda c: r[c]) for r in resp]


def comb2(n):
    return n * (n - 1) / 2


def clustering_scores(true_labels, pred_labels, xs):
    classes = sorted(set(true_labels))
    clusters = sorted(set(pred_labels))
    table = {(c, l): 0 for c in clusters for l in classes}
    for p, t in zip(pred_labels, true_labels):
        table[(p, t)] += 1
    row_sums = {c: sum(table[(c, l)] for l in classes) for c in clusters}
    col_sums = {l: sum(table[(c, l)] for c in clusters) for l in classes}
    n = len(true_labels)
    sum_comb = sum(comb2(v) for v in table.values())
    expected = sum(comb2(v) for v in row_sums.values()) * sum(comb2(v) for v in col_sums.values()) / comb2(n)
    max_index = 0.5 * (sum(comb2(v) for v in row_sums.values()) + sum(comb2(v) for v in col_sums.values()))
    ari = (sum_comb - expected) / (max_index - expected or 1.0)
    mi = sum((v / n) * math.log((v * n) / (row_sums[c] * col_sums[l])) for (c, l), v in table.items() if v)
    hc = -sum((v / n) * math.log(v / n) for v in row_sums.values() if v)
    hl = -sum((v / n) * math.log(v / n) for v in col_sums.values() if v)
    nmi = mi / math.sqrt((hc or 1.0) * (hl or 1.0))
    return {"ari": ari, "nmi": nmi, "silhouette": silhouette(xs, pred_labels), "confusion": table}


def sample_rows(rows, max_n=5000):
    if len(rows) <= max_n:
        return rows
    rng = random.Random(0)
    return [rows[i] for i in sorted(rng.sample(range(len(rows)), max_n))]


def silhouette(xs, labels, max_n=400):
    rng = random.Random(0)
    idx = list(range(len(xs)))
    if len(idx) > max_n:
        idx = sorted(rng.sample(idx, max_n))
    by_label = defaultdict(list)
    for i in idx:
        by_label[labels[i]].append(i)
    scores = []
    for i in idx:
        own = by_label[labels[i]]
        a = sum(math.sqrt(sqdist(xs[i], xs[j])) for j in own if j != i) / max(len(own) - 1, 1)
        b = min(
            sum(math.sqrt(sqdist(xs[i], xs[j])) for j in members) / len(members)
            for label, members in by_label.items()
            if label != labels[i]
        )
        scores.append((b - a) / max(a, b, 1e-9))
    return sum(scores) / len(scores)


def classify_threshold(row, overrides=None):
    thresholds = {"dict": 0.80, "func": 50.0, "layer": 7.0, "sparsity": 0.45}
    if overrides:
        thresholds.update(overrides)
    if row["peak_consistency_main"] >= thresholds["dict"] and row["n_distinct_peaks"] <= 1:
        return "Semantic (Dictionary)"
    if row["func_vs_sem_pct"] >= thresholds["func"] and row["conf_F"] >= 0.90 and row["layer"] >= thresholds["layer"]:
        return 'Say "X"'
    if row["sparsity_median"] < thresholds["sparsity"]:
        return "Relationship"
    if row["layer"] <= 3 or (1 - row["conf_F"]) >= 0.50 or row["func_vs_sem_pct"] < thresholds["func"]:
        return "Semantic (Concept)"
    return "Ambiguous/Review"


def sensitivity(rows):
    baseline = [classify_threshold(row) for row in rows]
    specs = {"dict": 0.80, "func": 50.0, "sparsity": 0.45, "layer": 7.0}
    windows = {"dict": 0.05, "func": 5.0, "sparsity": 0.05, "layer": 0.5}
    fields = {"dict": "peak_consistency_main", "func": "func_vs_sem_pct", "sparsity": "sparsity_median", "layer": "layer"}
    out = []
    for name, value in specs.items():
        for direction, scale in [("minus_10pct", 0.9), ("plus_10pct", 1.1)]:
            shifted = [classify_threshold(row, {name: value * scale}) for row in rows]
            flips = sum(a != b for a, b in zip(baseline, shifted))
            out.append({"threshold": name, "perturbation": direction, "flip_rate": flips / len(rows)})
        near = sum(abs(row[fields[name]] - value) <= windows[name] for row in rows)
        out.append({"threshold": name, "perturbation": "near_boundary", "flip_rate": near / len(rows)})
    return out


def png(path, width, height, pixels):
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(raw, 9))
    data += chunk(b"IEND", b"")
    path.write_bytes(data)


def draw_rect(img, x0, y0, x1, y1, color):
    h, w = len(img), len(img[0]) // 3
    for y in range(max(0, y0), min(h, y1)):
        row = img[y]
        for x in range(max(0, x0), min(w, x1)):
            row[3 * x:3 * x + 3] = color


def draw_summary(path, rows, pcs, labels, clusters):
    width, height = 1200, 900
    img = [bytearray([255, 255, 255] * width) for _ in range(height)]
    classes = sorted(set(labels))
    palette = {label: COLORS[i % len(COLORS)] for i, label in enumerate(classes)}
    draw_rect(img, 0, 0, width, height, (250, 250, 250))
    panels = [(40, 40, 560, 410), (640, 40, 1160, 410), (40, 490, 560, 860), (640, 490, 1160, 860)]
    for panel in panels:
        draw_rect(img, *panel, (255, 255, 255))
    hist_keys = ["peak_consistency_main", "func_vs_sem_pct", "sparsity_median", "layer"]
    thresholds = {
        "peak_consistency_main": 0.80,
        "func_vs_sem_pct": 50.0,
        "sparsity_median": 0.45,
        "layer": 7.0,
    }
    for i, key in enumerate(hist_keys):
        x0, y0, x1, y1 = panels[0]
        sub_y0 = y0 + i * 90 + 10
        vals = [row[key] for row in rows]
        lo, hi = min(vals), max(vals)
        bins = [0] * 40
        for val in vals:
            idx = min(39, int((val - lo) / ((hi - lo) or 1) * 39))
            bins[idx] += 1
        m = max(bins)
        for b, count in enumerate(bins):
            bx0 = x0 + 20 + b * 12
            bar_h = int(70 * count / m)
            draw_rect(img, bx0, sub_y0 + 70 - bar_h, bx0 + 10, sub_y0 + 70, (120, 120, 120))
        tx = x0 + 20 + int((thresholds[key] - lo) / ((hi - lo) or 1) * 480)
        draw_rect(img, tx, sub_y0, tx + 3, sub_y0 + 72, (220, 40, 40))
    xs = [p[0] for p in pcs]
    ys = [p[1] for p in pcs]
    panel = panels[1]
    x0, y0, x1, y1 = panel
    sample = range(0, len(rows), max(1, len(rows) // 2500))
    for i in sample:
        x = x0 + 20 + int((xs[i] - min(xs)) / ((max(xs) - min(xs)) or 1) * (x1 - x0 - 40))
        y = y1 - 20 - int((ys[i] - min(ys)) / ((max(ys) - min(ys)) or 1) * (y1 - y0 - 40))
        draw_rect(img, x - 1, y - 1, x + 2, y + 2, palette[labels[i]])

    datasets = sorted(set(row["dataset"] for row in rows))
    x0, y0, x1, y1 = panels[2]
    cell_w = (x1 - x0) // 3
    cell_h = (y1 - y0) // 2
    for d_i, dataset in enumerate(datasets):
        px0 = x0 + (d_i % 3) * cell_w + 10
        py0 = y0 + (d_i // 3) * cell_h + 10
        px1 = px0 + cell_w - 20
        py1 = py0 + cell_h - 20
        draw_rect(img, px0, py0, px1, py1, (252, 252, 252))
        members = [i for i, row in enumerate(rows) if row["dataset"] == dataset]
        for i in members[::max(1, len(members) // 450)]:
            x = px0 + 6 + int((xs[i] - min(xs)) / ((max(xs) - min(xs)) or 1) * (px1 - px0 - 12))
            y = py1 - 6 - int((ys[i] - min(ys)) / ((max(ys) - min(ys)) or 1) * (py1 - py0 - 12))
            draw_rect(img, x - 1, y - 1, x + 2, y + 2, palette[labels[i]])

    x0, y0, x1, y1 = panels[3]
    cluster_ids = sorted(set(clusters))
    table = Counter(zip(clusters, labels))
    max_count = max(table.values()) if table else 1
    cell_w = (x1 - x0 - 40) // len(classes)
    cell_h = (y1 - y0 - 40) // len(cluster_ids)
    for r, cluster_id in enumerate(cluster_ids):
        for c, label in enumerate(classes):
            count = table[(cluster_id, label)]
            shade = 255 - int(220 * count / max_count)
            draw_rect(
                img,
                x0 + 20 + c * cell_w,
                y0 + 20 + r * cell_h,
                x0 + 20 + (c + 1) * cell_w - 2,
                y0 + 20 + (r + 1) * cell_h - 2,
                (255, shade, shade),
            )
    png(path, width, height, img)


def analyze_frame(name, rows):
    sampled = sample_rows(rows)
    xs = standardize(sampled)
    labels = [row["class"] for row in sampled]
    results = []
    for algo in ["kmeans", "gmm"]:
        for k in [3, 4, 5, 6]:
            pred = kmeans(xs, k)[0] if algo == "kmeans" else gmm_diag(xs, k)
            scores = clustering_scores(labels, pred, xs)
            results.append(
                {
                    "frame": name,
                    "algorithm": algo,
                    "k": k,
                    "n_clustered": len(sampled),
                    **{m: scores[m] for m in ["ari", "nmi", "silhouette"]},
                }
            )
    return results, first_two_pcs(xs), sampled


def main():
    repo = Path(__file__).resolve().parents[2]
    out_dir = repo / "output" / "research"
    rows = load_rows(out_dir / "feature_manifest.csv")
    deduped = dedupe(rows)
    print(f"Loaded {len(rows)} rows and {len(deduped)} deduped features", flush=True)
    all_results, all_pcs, _sampled_rows = analyze_frame("all_rows", rows)
    print("Finished all-row clustering", flush=True)
    dedup_results, dedup_pcs, sampled_deduped = analyze_frame("deduped", deduped)
    print("Finished deduped clustering", flush=True)
    all_results.extend(dedup_results)
    per_dataset = []
    for dataset in sorted({row["dataset"] for row in rows}):
        subset = sample_rows([row for row in rows if row["dataset"] == dataset])
        xs = standardize(subset)
        labels = [row["class"] for row in subset]
        for algo in ["kmeans", "gmm"]:
            pred = kmeans(xs, 4)[0] if algo == "kmeans" else gmm_diag(xs, 4)
            scores = clustering_scores(labels, pred, xs)
            per_dataset.append(
                {
                    "dataset": dataset,
                    "algorithm": algo,
                    "k": 4,
                    "n_clustered": len(subset),
                    **{m: scores[m] for m in ["ari", "nmi", "silhouette"]},
                }
            )
        print(f"Finished {dataset}", flush=True)
    sens = sensitivity(rows)
    summary_clusters = kmeans(standardize(sampled_deduped), 4)[0]
    draw_summary(
        out_dir / "feature_classes_naturalness.png",
        sampled_deduped,
        dedup_pcs,
        [row["class"] for row in sampled_deduped],
        summary_clusters,
    )
    payload = {
        "n_all_rows": len(rows),
        "n_deduped": len(deduped),
        "class_counts_all": Counter(row["class"] for row in rows),
        "class_counts_deduped": Counter(row["class"] for row in deduped),
        "clustering": all_results,
        "per_dataset": per_dataset,
        "sensitivity": sens,
    }
    with (out_dir / "feature_clustering_results.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    with (out_dir / "feature_clustering_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "frame",
                "algorithm",
                "k",
                "n_clustered",
                "ari",
                "nmi",
                "silhouette",
            ],
        )
        writer.writeheader()
        writer.writerows(all_results)
    print(json.dumps(payload, indent=2)[:4000])


if __name__ == "__main__":
    main()
