"""Q2 预注册表（**必须在任何 Top-3 选择之前运行**）。

只读 `1.csv` 的列名做存在性校验；不读 2.csv / 4.csv / 6.csv 的任何数值，
因此本表与后续选择结果在信息上独立（顺序可由文件 mtime/哈希与实验记录核验）。

命中率分母 = 预注册维度数 × 3 个 Top-3 席位；未预注册（探索性）维度不进入命中率。
`expected_signs` 是**先验方向**（+1 表示该化合物越高、该感官越强；-1 反之），
来自既有风味化学机制，不是从本数据拟合出来的。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import q2_common as Q  # noqa: E402

# dim -> (expected compounds, expected signs, rationale)
PREREG: dict[str, tuple[list[str], list[int], str]] = {}


def _add(dim, compounds, signs, rationale):
    assert len(compounds) == len(signs), dim
    PREREG[dim] = (compounds, signs, rationale)


# ---------------- Aroma：麦芽族 ----------------
_add("A_malt_all",
     ["X3.methylbutanal", "X2.3.butanedione", "methylpyrazine", "furfural", "X5.methylfurfural"],
     [1, 1, 1, 1, 1],
     "麦芽香综合=Strecker 醛(麦芽/坚果)、二酮(奶油)、吡嗪(烘烤)、糠醛类(焦糖/面包)等已知麦芽源香气标志")
_add("A_malt_grain",
     ["X3.methylbutanal", "X2.6.dimethyl.pyrazine", "methylpyrazine"],
     [1, 1, 1],
     "谷粒/生麦芽香与 Strecker 醛及烷基吡嗪（烘烤谷物）一致")
_add("A_malt_bread",
     ["X3.methylbutanal", "furfural", "X2.acetylpyrrole"],
     [1, 1, 1],
     "面包皮香=美拉德产物（Strecker 醛、糠醛、乙酰吡咯）")
_add("A_malt_cara",
     ["furfural", "X5.methylfurfural", "isomaltol", "X2.acetylfuran"],
     [1, 1, 1, 1],
     "焦糖香=糖类热降解产物（糠醛、5-甲基糠醛、异麦芽酚、乙酰呋喃）")
_add("A_malt_burn",
     ["X4.ethyl.phenol", "X4.ethyl.guaiacol", "ortho.cresol", "eugenol"],
     [1, 1, 1, 1],
     "该维在 8.xlsx 的 CleanName_Paper 为 'Malt - smoked'：烟熏/酚类香来自 4-乙基苯酚、4-乙基愈创木酚、邻甲酚、丁子香酚；"
     "注：A/F 前缀与题面 'Malt - smoked' 的对应关系由 8.xlsx Sensory names 给出，非本数据推断")
# ---------------- Aroma：酒花族 ----------------
_add("A_hops_all",
     ["alpha.humulene", "E.caryophyllene", "linalool", "geraniol", "citronellol", "limonene"],
     [1, 1, 1, 1, 1, 1],
     "酒花香综合=酒花萜烯(葎草烯/石竹烯)与萜醇(芳樟醇/香叶醇/香茅醇)及柠檬烯")
_add("A_hops_citrus",
     ["linalool", "geraniol", "citronellol", "limonene"],
     [1, 1, 1, 1],
     "柑橘酒花香=芳樟醇、香叶醇、香茅醇、柠檬烯（酒花精油单萜/单萜醇）")
_add("A_hops_tropical",
     ["linalool", "geraniol", "citronellol", "limonene", "X.E..beta.farnesene"],
     [1, 1, 1, 1, 1],
     "热带果香=硫醇类在 1.csv 中不可得，本表退到酒花单萜醇与 β-法尼烯；β-法尼烯方向为弱先验")
_add("A_hops_noble",
     ["alpha.humulene", "E.caryophyllene", "beta.humulene"],
     [1, 1, 1],
     "贵族酒花/草香=葎草烯与石竹烯（酒花树脂萜烯），8.xlsx 中该维名 'Hops - grassy'")
_add("A_hops_woody",
     ["E.caryophyllene", "alpha.humulene", "caryophyllene.oxide", "humulene.epoxide.II"],
     [1, 1, 1, 1],
     "木质香=倍半萜及其环氧化物（石竹烯、葎草烯、石竹烯氧化物、葎草烯环氧化物）")
# ---------------- Aroma：酯类 ----------------
_add("A_esters_all",
     ["ethyl_acetate", "isopentyl_acetate", "ethyl_hexanoate", "ethyl_octanoate",
      "phenethyl_acetate", "ethyl.butyrate"],
     [1, 1, 1, 1, 1, 1],
     "酯香综合=乙酸乙酯、乙酸异戊酯、己酸/辛酸乙酯、乙酸苯乙酯、丁酸乙酯等酵母酯")
_add("A_esters_ethac",
     ["ethyl_acetate", "ethyl_propionate", "ethyl.butyrate"],
     [1, 1, 1],
     "该维在 8.xlsx 中为 'Esters - nail polish'：指甲油味=乙酸乙酯（溶剂感），丙酸/丁酸乙酯为同族弱先验")
_add("A_esters_isoaa",
     ["isopentyl_acetate", "isopentyl.butanoate", "isoamyl_alcohol"],
     [1, 1, 1],
     "该维在 8.xlsx 中为 'Esters - banana'：香蕉味=乙酸异戊酯（isoamyl acetate）；异戊醇为其前体醇")
_add("A_esters_flower",
     ["phenethyl_acetate", "phenethyl_alcohol", "linalool", "geraniol"],
     [1, 1, 1, 1],
     "花香=乙酸苯乙酯/苯乙醇（玫瑰）与芳樟醇/香叶醇（花香萜醇）")
_add("A_esters_fruity",
     ["ethyl.butyrate", "ethyl_hexanoate", "ethyl_octanoate", "isopentyl_acetate"],
     [1, 1, 1, 1],
     "果香=短中链脂肪酸乙酯（丁酸/己酸/辛酸乙酯）与乙酸异戊酯")
# ---------------- Flavour：同族（F_ 前缀） ----------------
for _dim, _comp, _sign, _why in [
    ("F_malt_all", ["X3.methylbutanal", "X2.3.butanedione", "methylpyrazine", "furfural", "X5.methylfurfural"],
     [1, 1, 1, 1, 1], "风味版麦芽综合，机制同 A_malt_all（麦芽源香气标志）"),
    ("F_malt_grain", ["X3.methylbutanal", "X2.6.dimethyl.pyrazine", "methylpyrazine"],
     [1, 1, 1], "风味版谷粒香，机制同 A_malt_grain"),
    ("F_malt_bread", ["X3.methylbutanal", "furfural", "X2.acetylpyrrole"],
     [1, 1, 1], "风味版面包香，机制同 A_malt_bread"),
    ("F_malt_cara", ["furfural", "X5.methylfurfural", "isomaltol", "X2.acetylfuran"],
     [1, 1, 1, 1], "风味版焦糖香，机制同 A_malt_cara"),
    ("F_malt_burn", ["X4.ethyl.phenol", "X4.ethyl.guaiacol", "ortho.cresol", "eugenol"],
     [1, 1, 1, 1], "风味版烟熏（'Malt - smoked'），机制同 A_malt_burn"),
    ("F_hops_all", ["alpha.humulene", "E.caryophyllene", "linalool", "geraniol", "citronellol", "limonene"],
     [1, 1, 1, 1, 1, 1], "风味版酒花综合，机制同 A_hops_all"),
    ("F_hops_citrus", ["linalool", "geraniol", "citronellol", "limonene"],
     [1, 1, 1, 1], "风味版柑橘酒花，机制同 A_hops_citrus"),
    ("F_hops_tropical", ["linalool", "geraniol", "citronellol", "limonene", "X.E..beta.farnesene"],
     [1, 1, 1, 1, 1], "风味版热带果香，机制同 A_hops_tropical"),
    ("F_hops_noble", ["alpha.humulene", "E.caryophyllene", "beta.humulene"],
     [1, 1, 1], "风味版草香/贵族酒花，机制同 A_hops_noble"),
    ("F_hops_woody", ["E.caryophyllene", "alpha.humulene", "caryophyllene.oxide", "humulene.epoxide.II"],
     [1, 1, 1, 1], "风味版木质香，机制同 A_hops_woody"),
    ("F_esters_all", ["ethyl_acetate", "isopentyl_acetate", "ethyl_hexanoate", "ethyl_octanoate",
                      "phenethyl_acetate", "ethyl.butyrate"],
     [1, 1, 1, 1, 1, 1], "风味版酯香综合，机制同 A_esters_all"),
    ("F_esters_ethac", ["ethyl_acetate", "ethyl_propionate", "ethyl.butyrate"],
     [1, 1, 1], "风味版指甲油味，机制同 A_esters_ethac"),
    ("F_esters_isoaa", ["isopentyl_acetate", "isopentyl.butanoate", "isoamyl_alcohol"],
     [1, 1, 1], "风味版香蕉味，机制同 A_esters_isoaa"),
    ("F_esters_flower", ["phenethyl_acetate", "phenethyl_alcohol", "linalool", "geraniol"],
     [1, 1, 1, 1], "风味版花香，机制同 A_esters_flower"),
    ("F_esters_fruity", ["ethyl.butyrate", "ethyl_hexanoate", "ethyl_octanoate", "isopentyl_acetate"],
     [1, 1, 1, 1], "风味版果香，机制同 A_esters_fruity"),
]:
    _add(_dim, _comp, _sign, _why)
# ---------------- Palate / 缺陷 / 口感 ----------------
_add("acidity", ["lactic_acid.mg.L.", "acetic_acid.g.L.", "pH"],
     [1, 1, -1], "酸感=乳酸/乙酸浓度；pH 越低酸感越强（预期负号）")
_add("bitternes", ["bitterness"], [1],
     "苦味主要由异α-酸决定，但 1.csv 无独立 iso-α-acid 列，仅有实测 bitterness 列；因此只预注册该直接测量列")
_add("sweetness", ["unfermentables", "glycerol", "ethanol..v.v."],
     [1, 1, 1], "甜感=未发酵糖/残糖、甘油（甜味与黏稠感）、乙醇（甜感增强）")
_add("X4vg", ["X4VG"], [1], "4-乙烯基愈创木酚（4VG）直接对应其感官维（酚/香料味）")
_add("diacetyl", ["X2.3.butanedione"], [1], "双乙酰（2,3-丁二酮）直接对应奶油/黄油缺陷")
_add("dms", ["DMS"], [1], "二甲基硫（DMS）直接对应煮玉米/蔬菜缺陷")
_add("metallic", ["iron"], [1], "金属味=铁离子（氧化催化与金属味）；1.csv 有 iron 列")
_add("stale_hops", ["X.E..2.nonenal", "X3.methyl.2.butenal", "X5.methylfurfural", "furfural"],
     [1, 1, 1, 1], "陈化酒花/纸板味=反-2-壬烯醛、3-甲基-2-丁烯醛、糠醛类陈化羰基")
_add("t2n", ["X.E..2.nonenal"], [1], "反-2-壬烯醛（trans-2-nonenal）直接对应纸板/陈旧缺陷")
_add("orange", ["limonene", "linalool", "X3Z.hexenol"],
     [1, 1, 1], "橙香=柠檬烯为主，芳樟醇/顺-3-己烯醇为柑橘类辅证（后两者弱先验）")
_add("coriander", ["linalool", "geraniol"],
     [1, 1], "芫荽籽香=芳樟醇（芫荽籽主成分），香叶醇为同族弱先验")
_add("clove", ["eugenol", "X4.ethyl.guaiacol", "X4.ethyl.phenol"],
     [1, 1, 1], "丁香/酚香=丁子香酚；4-乙基愈创木酚与 4-乙基苯酚为酚类同族（较弱先验）")
_add("lactic", ["lactic_acid.mg.L."], [1], "乳酸味=乳酸浓度直接测量列")
_add("acetic", ["acetic_acid.g.L."], [1], "醋酸味=乙酸浓度直接测量列")
_add("barnyard", ["X4.ethyl.phenol", "X4.ethyl.guaiacol"],
     [1, 1], "马厩/腥味=4-乙基苯酚与 4-乙基愈创木酚（Brettanomyces 酚类缺陷）")
_add("alcohol", ["ethanol..v.v.", "isoamyl_alcohol", "isobutanol", "X1.propanol"],
     [1, 1, 1, 1], "酒精感=乙醇为主，高级醇（异戊醇/异丁醇/正丙醇）为溶剂/上头感同族")
_add("body", ["glycerol", "protein.g.L.", "betaglucan.mg.L.", "unfermentables"],
     [1, 1, 1, 1], "酒体/醇厚=甘油、蛋白、β-葡聚糖（黏度）与未发酵物")
_add("co2", ["CO2.PSI."], [1], "碳酸感=CO2 压力直接测量列")

# 探索性维度：无单化合物先验，不进入命中率分母（如实声明）
EXPLORATORY = {
    "aftertaste": "余味是综合时间维度，无单一化合物先验；不预注册以避免事后合理化",
    "overall": "总体喜好为综合评分，无单一化合物先验；不预注册",
}


def main():
    feat_cols = set(C.feature_columns())
    missing = {}
    for dim, (comp, signs, why) in PREREG.items():
        bad = [c for c in comp if c not in feat_cols]
        if bad:
            missing[dim] = bad
    if missing:
        raise SystemExit(f"预注册化合物不在 1.csv 列中: {missing}")

    all_dims = list(C.TARGET_DIMS)
    unknown = set(PREREG) - set(all_dims)
    if unknown:
        raise SystemExit(f"预注册表含未知维度: {unknown}")

    rows = []
    for dim in all_dims:
        if dim in PREREG:
            comp, signs, why = PREREG[dim]
            rows.append({
                "dim": dim,
                "preregistered": True,
                "n_expected": len(comp),
                "expected_compounds": ";".join(comp),
                "expected_signs": ";".join(str(s) for s in signs),
                "rationale": why,
            })
        else:
            rows.append({
                "dim": dim, "preregistered": False, "n_expected": 0,
                "expected_compounds": "", "expected_signs": "",
                "rationale": EXPLORATORY.get(dim, "无可靠单化合物先验"),
            })
    df = pd.DataFrame(rows)
    out_csv = C.ROOT / "outputs" / "q2" / "preregistered_expectations.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8")

    sha = hashlib.sha256(out_csv.read_bytes()).hexdigest()
    n_prereg = int(df["preregistered"].sum())
    summary = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "csvPath": "outputs/q2/preregistered_expectations.csv",
        "csvSha256": sha,
        "n_dims_total": len(all_dims),
        "n_dims_preregistered": n_prereg,
        "n_dims_exploratory": len(all_dims) - n_prereg,
        "n_seats_preregistered": n_prereg * 3,
        "hit_rate_denominator": "n_dims_preregistered * 3 (final Top-3 seats on preregistered dims only)",
        "statement": (
            "本表在 Q2 任何选择方法运行之前生成；只读了 1.csv 的列名做存在性校验，"
            "未读 2.csv/4.csv/6.csv 的数值。命中率必须在选择结果产生之后用本表对照计算，"
            "阈值与维度集合不得事后调整。"),
        "sign_convention": "+1 = 该化合物越高、该感官维度越强；-1 = 相反",
        "exploratory_dims": sorted(EXPLORATORY),
    }
    (C.ROOT / "outputs" / "q2" / "preregistered_expectations.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nwrote {out_csv}")


if __name__ == "__main__":
    main()
