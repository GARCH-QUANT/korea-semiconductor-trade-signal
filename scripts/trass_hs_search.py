#!/usr/bin/env python3
"""
TRASS HS编码搜索脚本
功能：从已知4位码向下探索6位和10位子码，识别SSD/HBM相关候选编码
数据源：bandtrass.or.kr HS2022分类体系
依赖：requests, pyyaml
"""

import requests
import json
import yaml
import sys
import time
from pathlib import Path

# ===================== 配置区 =====================
CONFIG_PATH = Path(__file__).parent.parent / "config" / "hs_codes.yaml"
OUTPUT_PATH = Path(__file__).parent.parent / "config" / "hs_codes_explored.yaml"

# 已确认的4位父码（需探索其下级）
PARENT_CODES = {
    "8542": "전자집적회로（电子集成电路，HBM核心锚点）",
    "8523": "비휘발성 기억장치（非易失性存储介质，SSD候选）",
    "8486": "반도체 제조용 기계（半导体制造设备）",
    "8541": "반도체 디바이스（半导体器件）",
    "8471": "자동자료처리기기（自动资料处理器）",
}

# 搜索关键词（韩文）
KW_SSD = ["솔리드", "SSD", "메모리", "스토리지", "플래시", "반도체"]
KW_HBM = ["HBM", "고대역폭", "DRAM", "메모리", "집적회로", "밴드와이드"]
KW_CHIP = ["프로세서", "ASIC", "FPGA", "시스템", "시스템인"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.bandtrass.or.kr/hscode/hsCode.do",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
# ===================== 工具函数 =====================


def fetch_hs_codes(parent_code: str, digit: int) -> list[dict]:
    """
    抓取HS编码树
    digit: 4→gubun4, 6→gubun6, 10→gubun10
    """
    gubun_map = {4: "4", 6: "6", 10: "10"}
    gubun = gubun_map[digit]

    url = "https://www.bandtrass.or.kr/hscode/hsCode.do"
    data = {
        "command": "list",
        "gubun": gubun,
        "hscode": parent_code,
        "cYear": "2026",
    }

    resp = SESSION.post(url, data=data, timeout=20)
    resp.raise_for_status()
    items = json.loads(resp.text)

    results = []
    for item in items:
        results.append({
            "hscd": item.get("hscd", ""),
            "name_kor": item.get("gods_name_kor", ""),
            "parent": parent_code,
            "level": digit,
        })
    return results


def score_relevance(code: str, name: str, keywords: list[str]) -> int:
    """计算名称与关键词的匹配得分"""
    name_lower = name.lower()
    score = 0
    for kw in keywords:
        if kw.lower() in name_lower:
            score += 1
    return score


def explore_tree(parent_4: str, label: str) -> dict:
    """从4位码向下探索6位→10位，返回相关编码"""
    print(f"\n{'='*60}")
    print(f"探索 {parent_4} ({label})")
    print(f"{'='*60}")

    tree = {"4digit": parent_4, "6digit": [], "10digit": [], "relevant_6": [], "relevant_10": []}

    # Step1: 抓4位下的6位码
    print(f"  → 抓取6位子码...")
    try:
        codes_6 = fetch_hs_codes(parent_4, 6)
        tree["6digit"] = codes_6
        print(f"    共 {len(codes_6)} 个6位码")

        # 评估每个6位码与SSD/HBM的相关性
        for c6 in codes_6:
            score_ssd = score_relevance(c6["hscd"], c6["name_kor"], KW_SSD)
            score_hbm = score_relevance(c6["hscd"], c6["name_kor"], KW_HBM)
            c6["score_ssd"] = score_ssd
            c6["score_hbm"] = score_hbm
            c6["best_match"] = "SSD" if score_ssd > score_hbm else ("HBM" if score_hbm > 0 else "none")

            if score_ssd > 0 or score_hbm > 0:
                tree["relevant_6"].append(c6)
                print(f"    ★ [{c6['best_match']}] {c6['hscd']}  {c6['name_kor'][:50]}")

        time.sleep(0.5)

        # Step2: 对每个6位码，抓10位子码
        for c6 in codes_6:
            try:
                codes_10 = fetch_hs_codes(c6["hscd"], 10)
                tree["10digit"].extend(codes_10)
                print(f"  → {c6['hscd']}: {len(codes_10)} 个10位码")

                # 评估10位码相关性
                for c10 in codes_10:
                    score_ssd = score_relevance(c10["hscd"], c10["name_kor"], KW_SSD)
                    score_hbm = score_relevance(c10["hscd"], c10["name_kor"], KW_HBM)
                    c10["score_ssd"] = score_ssd
                    c10["score_hbm"] = score_hbm
                    c10["parent_6"] = c6["hscd"]

                    if score_ssd > 0 or score_hbm > 0:
                        tree["relevant_10"].append(c10)
                        print(f"      ★ {c10['hscd']}  {c10['name_kor'][:60]}")

                time.sleep(0.3)
            except Exception as e:
                print(f"  ✗ {c6['hscd']} 10位码抓取失败: {e}")

    except Exception as e:
        print(f"  ✗ 6位码抓取失败: {e}")

    return tree


def generate_summary(all_trees: list[dict]) -> dict:
    """生成探索结果摘要"""
    summary = {
        "exploration_date": time.strftime("%Y-%m-%d"),
        "ssd_candidates": [],
        "hbm_candidates": [],
        "needs_manual_review": [],
    }

    for tree in all_trees:
        for item in tree.get("relevant_6", []):
            if item["best_match"] == "SSD":
                summary["ssd_candidates"].append({
                    "hs_code": item["hscd"],
                    "name": item["name_kor"],
                    "parent_4digit": tree["4digit"],
                    "level": "6",
                    "confidence": "high" if item["score_ssd"] >= 2 else "medium",
                })
            elif item["best_match"] == "HBM":
                summary["hbm_candidates"].append({
                    "hs_code": item["hscd"],
                    "name": item["name_kor"],
                    "parent_4digit": tree["4digit"],
                    "level": "6",
                    "confidence": "high" if item["score_hbm"] >= 2 else "medium",
                })

        for item in tree.get("relevant_10", []):
            if item["score_ssd"] > 0 or item["score_hbm"] > 0:
                summary["needs_manual_review"].append({
                    "hs_code": item["hscd"],
                    "name": item["name_kor"],
                    "parent_6": item["parent_6"],
                    "likely_type": "SSD" if item["score_ssd"] > item["score_hbm"] else "HBM",
                })

    return summary


def main():
    print("=" * 60)
    print("TRASS HS编码探索脚本")
    print("目标：识别SSD/HBM相关6位和10位候选编码")
    print("=" * 60)

    all_trees = []

    for code_4, label in PARENT_CODES.items():
        tree = explore_tree(code_4, label)
        all_trees.append(tree)
        time.sleep(1)  # 礼貌性延迟

    # 生成摘要
    summary = generate_summary(all_trees)

    print("\n" + "=" * 60)
    print("探索结果摘要")
    print("=" * 60)
    print(f"\nSSD候选（6位）: {len(summary['ssd_candidates'])} 个")
    for c in summary["ssd_candidates"]:
        print(f"  {c['hs_code']}  {c['name'][:50]}  [confidence={c['confidence']}]")

    print(f"\nHBM候选（6位）: {len(summary['hbm_candidates'])} 个")
    for c in summary["hbm_candidates"]:
        print(f"  {c['hs_code']}  {c['name'][:50]}  [confidence={c['confidence']}]")

    print(f"\n需人工确认（10位）: {len(summary['needs_manual_review'])} 个")
    for c in summary["needs_manual_review"][:10]:
        print(f"  {c['hs_code']}  {c['name'][:50]}  [{c['likely_type']}]")

    # 保存结果
    output = {
        "exploration_date": summary["exploration_date"],
        "trees": all_trees,
        "summary": summary,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\n✓ 完整结果已保存至: {OUTPUT_PATH}")
    return output


if __name__ == "__main__":
    main()
