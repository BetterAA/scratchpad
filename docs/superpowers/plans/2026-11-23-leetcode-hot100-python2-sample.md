# LeetCode Hot 100 Python 2 Handbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a complete 100-question Markdown handbook for the official LeetCode Hot 100 study plan, with deliberate-practice prompts, concise explanations, and Python 2.7-compatible solution templates.

**Architecture:** Deliver one standalone Markdown file at `/Users/andy/openclaw-AA/codinglist/leetcode-hot100-python2-sample.md`. Keep all 17 official categories and question order. Put the problem statement, examples, and a writable thinking area before a collapsed `<details>` answer for every question.

**Tech Stack:** Markdown; Python 2.7-compatible LeetCode `class Solution` templates; Python 3 scripts used only for structural and lexical validation because the host has no Python 2 interpreter.

---

### Task 1: Create the complete 100-question handbook

**Files:**
- Create: `/Users/andy/openclaw-AA/codinglist/leetcode-hot100-python2-sample.md`

- [ ] **Step 1: Create the target directory and document shell**

Create `/Users/andy/openclaw-AA/codinglist` if it does not exist. Start the document with its purpose, the official source link, the Python 2.7 compatibility rule, difficulty legend, and a suggested review loop.

- [ ] **Step 2: Add all official questions in category order**

Use the complete official sequence from the study plan, preserving all 17 categories and all 100 questions. The first 20 questions are already represented in the document; append the remaining 80 questions without changing their order. The table below records the initial 20-question sequence used to establish the approved format.

| Category | Questions |
| --- | --- |
| 哈希 | 1 两数之和；49 字母异位词分组；128 最长连续序列 |
| 双指针 | 283 移动零；11 盛最多水的容器；15 三数之和；42 接雨水 |
| 滑动窗口 | 3 无重复字符的最长子串；438 找到字符串中所有字母异位词 |
| 子串 | 560 和为 K 的子数组；239 滑动窗口最大值；76 最小覆盖子串 |
| 普通数组 | 53 最大子数组和；56 合并区间；189 轮转数组；238 除了自身以外数组的乘积；41 缺失的第一个正数 |
| 矩阵 | 73 矩阵置零；54 螺旋矩阵；48 旋转图像 |

Each entry must include a Markdown checkbox, official `leetcode.cn/problems/<slug>/` link, difficulty, core pattern, a paraphrased problem description, at least one Input/Output example, a thinking area with prompts for solution/state or invariant/boundary/complexity, and one closed `<details>` block containing the step-by-step idea, time and space complexity, at least one concrete pitfall, and a Python 2.7 `class Solution` or question-specific design-class template.

- [ ] **Step 3: Keep every code template Python 2.7 compatible**

Use Python 2 method signatures and syntax throughout. Include `# -*- coding: utf-8 -*-` only when a code block contains Chinese comments. Do not use type annotations, f-strings, `dataclass`, `pathlib`, or Python 3-only dictionary and string APIs. Use `xrange` for large integer iteration where the template needs lazy iteration. Keep templates focused on the central algorithm rather than adding local input/output wrappers.

### Task 2: Validate the complete handbook against the design

**Files:**
- Read: `/Users/andy/openclaw-AA/local-text-editor/docs/superpowers/specs/2026-11-23-leetcode-hot100-python2-sample-design.md`
- Read: `/Users/andy/openclaw-AA/codinglist/leetcode-hot100-python2-sample.md`

- [ ] **Step 1: Verify the complete question inventory and order**

Run a Python 3 check that extracts Markdown headings matching `### <number>.` and asserts exactly 100 headings against the current official study-plan payload, including all 17 category headings.

- [ ] **Step 2: Verify required fields and links**

Check that each question section contains `题目描述`, `输入输出示例`, `Input`, `Output`, `我的思考区`, `解法`, `状态或不变量`, `边界情况`, `复杂度预估`, exactly one `<details>`/`</details>` pair, `难度`, `核心模式`, `思路`, `复杂度`, `易错点`, and a `python` code fence. Confirm that each details block comes after the thinking area and that every official link uses the expected `leetcode.cn/problems/` prefix.

- [ ] **Step 3: Scan for Python 3-only syntax markers**

Search the Markdown code blocks for `f"`, `f'`, `->`, `dataclass`, `pathlib`, `typing`, `nonlocal`, and `async` markers. Confirm that any `print` usage follows Python 2 statement syntax, or omit console output from the LeetCode templates entirely. Review any match manually before accepting the file.

- [ ] **Step 4: Review Markdown readability**

Confirm heading nesting, checkbox rendering, code fence closure, and that the file is readable as a standalone study sheet without relying on the editor application.

### Task 3: Hand off the complete handbook

**Files:**
- Read: `/Users/andy/openclaw-AA/codinglist/leetcode-hot100-python2-sample.md`

- [ ] **Step 1: Report the generated file and validation results**

Give the user the absolute file path, the 17 covered categories and 100-question count, the validation commands run, and any limitation caused by the absence of a Python 2 interpreter.

- [ ] **Step 2: Preserve the approved format for future additions**

Preserve the approved Python 2.7 style and field order if the user requests another separate question bank.
