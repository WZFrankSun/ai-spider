# Git 学习文档：从本项目实战提炼

> 这份文档不是通用 Git 教程，而是**本项目（ai-spider）实际踩过的坑和验证过的做法**。
> 每个章节都对应一次真实经历，命令都是实际执行过的。

---

## 目录

1. [核心概念：三个哈希、一个指针](#1-核心概念三个哈希一个指针)
2. [改写历史：一次真实的 force push](#2-改写历史一次真实的-force-push)
3. [分支协同：M1–M9 的九轮循环](#3-分支协同m1m9-的九轮循环)
4. [踩坑清单：六个真实错误](#4-踩坑清单六个真实错误)
5. [备份与找回：三种后悔药](#5-备份与找回三种后悔药)
6. [标签策略：本次项目的演进](#6-标签策略本次项目的演进)
7. [推送：PowerShell 环境的可靠做法](#7-推送powershell-环境的可靠做法)
8. [日常命令速查（PowerShell 版）](#8-日常命令速查powershell-版)
9. [协作守则](#9-协作守则)

---

## 1. 核心概念：三个哈希、一个指针

### 三个哈希

| 对象 | 是什么 | 本项目实例 |
|---|---|---|
| **blob** | 文件内容的指纹 | 某个 `.py` 文件的内容哈希 |
| **tree** | 目录下所有条目的指纹 | `app/monitoring/` 整个目录的哈希 |
| **commit** | 一次快照：树 + 父提交 + 作者 + 消息 | `796e2bb` 合并 M9 |

**关键认知：内容决定哈希。** 同样的内容在任何仓库、任何分支，哈希都一样。

### 一个指针

**分支（branch）就是一个指向某个 commit 的可移动指针。**

这是理解本次所有困惑的钥匙：

```
master ──────► 796e2bb ──► 80116ed ──► ...
feature/m7 ──► 32d518d
```

`git branch` 做的事只是**移动指针**，不复制任何文件、不改任何提交。这就是为什么分支创建和删除都是瞬间完成的。

### 树哈希是判断「内容是否相同」的可靠依据

本次做历史整理时，我用这个方法验证「改写历史有没有丢东西」：

```powershell
git rev-parse 41e67bd^{tree}
git rev-parse 3542edb^{tree}
```

输出**完全相同** → 说明 `41e67bd` 和 `3542edb` 产出的文件内容一模一样，只是提交消息和哈希不同。

**这是比 `git diff` 更可靠的验证方式**，因为它不依赖 diff 的显示逻辑，直接比对内容指纹。

> 本项目实际结果：
> | 旧提交 | 新提交 | 树哈希 |
> |---|---|---|
> | `41e67bd` | `3542edb` | `f4c2da01...` 相同 |
> | `aa8b2f7` | `3f89485` | `4fda1fb2...` 相同 |

---

## 2. 改写历史：一次真实的 force push

### 背景

本项目 11-23 做了一次**历史整理**：原本的提交链有语义不清的问题（两个提交消息一模一样），想重写成「初始提交 / 清理 / 退役框架」这样三段清晰的。

改写方式不是 rebase，而是用 plumbing 命令**直接构造提交对象**：

```powershell
git commit-tree <tree> -p <parent> -m "提交信息"
git update-ref refs/heads/master <new-commit> <old-commit>
```

### 关键：先建备份

改写前**必须**留后路：

```powershell
git branch backup/pre-rebase aa8b2f7
git tag backup-before-rebase-11.23 aa8b2f7
```

本次两个都建了 —— 后来证明是必要的。

### 改写后 `git branch -d` 报错

```powershell
git branch -d backup/pre-rebase
# error: The branch 'backup/pre-rebase' is not fully merged.
```

**原因**：`git branch -d` 判断「是否已合并」的依据是**提交哈希的可达性**，不是内容是否相同。改写历史后，旧哈希在 master 上已经不存在了 → Git 认为「没合并」。

**但内容其实没丢**。验证方法：

```powershell
git cherry master backup/pre-rebase
# + 41e67bd    ← 加号表示"master 上没有等价物"
```

`git cherry` 也是比哈希（patch-id），重写提交信息后 patch-id 也会变，所以同样判不出等价。

**最终确认方法是比树哈希**（见上一节）。确认无丢失后，用 `-D` 强删：

```powershell
git branch -D backup/pre-rebase
```

### force push 的连锁反应

```powershell
git push --force origin master
# + f771b89...3f89485 master -> master (forced update)
```

远程的旧提交被覆盖后，**别人如果已经拉取过，会出现本地与远程分叉**。

**本项目的教训**：这次操作在单人项目里没造成问题，但如果有协作者，必须先通知，或者改用「不重写历史」的方案（见第 9 节）。

### 一个意外的收获

force push 过程中**旧对象并没有立刻消失**。Git 对象库还留着它们，只是不可达（dangling）：

```powershell
git fsck --lost-found --no-progress
# dangling tree 036070894430bf53929999481ad030a38e9acb2f
# dangling tag bc227529ec079a4107ca3b89b6844c8fc2538724
```

这些可以用 `git fsck --lost-found` 找回，**在 gc 之前**。

---

## 3. 分支协同：M1–M9 的九轮循环

### 本项目实际采用的形态

```
master ──────────────────────────────────────────► (最终)
         ╲
          feature/m1-postal-utils ──────► 合并 + tag m1-postal-utils
          feature/m2-header-readback ───► 合并 + tag m2-header-readback
          ...
          feature/m9-dom-confirmed-unavailable ──► 合并 + tag m9-...
```

**每个模块一个分支，一次循环九轮。**

### 标准循环

```powershell
# ① 切分支 + 同步最新 master
git checkout feature/mX-xxx
git rebase master

# ② （编码、测试、提交）

# ③ 验收
git log -1 --oneline
git show --stat HEAD
git diff master..HEAD --stat

# ④ 合并 + 打 tag + 删分支
git checkout master
git merge --no-ff feature/mX-xxx
git tag mX-xxx
git branch -d feature/mX-xxx
```

### 关键点 1：`rebase` 让分支拿到最新 master

分支是从某个时间点拉出的，不 rebase 就拿不到后续合并的内容。

```powershell
git rebase master
```

**原理**：把当前分支的提交「摘下来」，接到 master 最新端点上，生成新哈希。

**为什么本项目必须先 rebase**：M2 依赖 M1 新增的 `postal_codes.py`，不 rebase Codex 会报「找不到模块」。

**安全性**：rebase 会在分支上**重放提交**。如果分支已有提交且与 master 改了同一处，会冲突：

```powershell
git status              # 看冲突文件
# 手动解决后
git add <文件>
git rebase --continue
# 搞不定就
git rebase --abort      # 退回原状
```

### 关键点 2：`--no-ff` 保留分支痕迹

```powershell
git merge --no-ff feature/mX-xxx
```

**不加 `--no-ff` 的话**：如果 master 上已经有该分支的所有提交，Git 会做 fast-forward，master 直接指向分支 tip，**历史里看不到「这个提交来自哪个分支」**。

**加了 `--no-ff` 之后**：生成一个合并提交，历史呈现为分叉再汇合：

```
*   796e2bb (tag: m9-...) Merge branch 'feature/m9-...'
|\
| * 370a431 M9 库存风险判定...
|/
*   80116ed (tag: m8-...) Merge branch 'feature/m8-...'
```

**本项目最终历史长这样**（`git log --graph --oneline`），每个模块的边界一目了然 —— 这正是选 `--no-ff` 的理由。

### 关键点 3：rebase 后必须再合并

```powershell
git rebase master          # 分支内容更新
git checkout master
git merge --no-ff feature/mX-xxx
```

**顺序反了会出问题**：如果先 merge 再 rebase，master 上已经有了旧版本的提交，rebase 过去会产生重复提交。

---

## 4. 踩坑清单：六个真实错误

### 坑 1：以为没合并，其实已经合了

**现象**：

```powershell
git checkout master
git merge --no-ff feature/m1-postal-utils
# merge: feature/m1-postal-utils - not something we can merge
```

**真相**：merge 已经成功过了，而且分支已被删除。

**排查方法 —— reflog**：

```powershell
git reflog --date=format:"%m-%d %H:%M"
```

```
15:16:37  commit: 新增 M1 邮编规范化与回读匹配工具
15:20:51  checkout: moving from feature/m2-header-readback to master
15:23:23  merge feature/m1-postal-utils: Merge made by the 'ort' strategy.
```

**reflog 记录了 HEAD 的每一次移动**，包括谁在什么时候 merge、checkout、rebase。这是排查「我的操作去哪了」的第一工具。

**根因**：协作方（Codex）也执行了 merge。教训是**在给 AI 的提示词里要明确边界**：

```
【工作范围】
- 只在当前分支 feature/mX-xxx 上工作
- 完成后提交，但不要切分支、不要 merge、不要删除分支、不要 push
- 合并到 master 由用户来执行
```

### 坑 2：PowerShell 里用 bash 命令

```powershell
git status -sb | head -1
# head : 无法将"head"项识别为 cmdlet...
```

**原因**：`head`/`grep` 是 Unix 命令，PowerShell 没有。

**PowerShell 对照表**：

| 用途 | bash | PowerShell |
|---|---|---|
| 取前 N 行 | `\| head -1` | 直接不用管道，或 `\| Select-Object -First 1` |
| 文本过滤 | `\| grep "x"` | `\| Select-String "x"` |
| 计数 | `\| grep -c "x"` | `(\| Select-String "x").Count` |
| 文件查找 | `find . -name "*.py"` | `Get-ChildItem -Recurse -Filter "*.py"` |
| 进程结束 | `kill -9 PID` | `Stop-Process -Id PID -Force` |

**教训**：给命令前先确认用户的 shell。本项目终端是 PowerShell，我早期给的 bash 命令让她白试了几次。

### 坑 3：以为「回滚 = 回到旧版本」，结果残留 8 个文件

**需求**：把代码恢复到最近一次 commit，同时保留未跟踪文件。

**执行**：

```powershell
git restore --source=HEAD --staged --worktree -- .
```

**为什么不用 `git reset --hard`**：`reset --hard` 在某些场景会连带清理未跟踪内容，而 `restore` 精确作用于已跟踪文件。

**结果**：8 个未跟踪文件保留、已跟踪文件全部回到 HEAD、工作区干净。

**遗留疑问**：那 8 个文件为什么「从未 add」？排查发现它们来自 `refs/codex/turn-diffs/checkpoints/...` —— 某个工具的工作区快照引用，不是正常 commit：

```powershell
git show-ref | Select-String "codex"
# refs/codex/turn-diffs/checkpoints/98b850ae.../f88bc48b-...
# 指向类型：tree（不是 commit）
git cat-file -t dc11a1a1072b0ca500d07ab70736a73e8761a281
# tree
```

**教训**：文件不在 Git 里 ≠ 文件没价值。要判断来源，看 `git log --all -- <路径>` 和 `git fsck --lost-found`。

### 坑 4：`git add -A` 越界

**场景**：做任务 A 时执行了 `git add -A`，把会话前就存在的 25 个文件的改动也一并暂存了。

**为什么是问题**：暂存区混入了不属于本次任务的内容，用户 review 时难以分辨。

**本项目的处理**：后来改用「只暂存本次涉及的文件」，并用

```powershell
git diff --cached --stat
```

在提交前核对范围。

**教训**：`git add -A` 在多人协作或存在他人未完成工作时很危险。宁可多写几个文件名。

### 坑 5：commit message 出现编码损坏

**现象**：

```
- 保留历史证据，新 004 迁移建立 deleted_product_ids 表
```

三个坏字节。原因是 heredoc 里混入了非 ASCII 字符。

**检测**：

```powershell
git log -1 --format=%B > msg_check.txt
python -c "d=open('msg_check.txt','rb').read(); t=d.decode('utf-8',errors='replace'); print(t.count('\ufffd'))"
```

**修复**（不改文件内容，只改消息）：

```powershell
git commit --amend -F msg_fixed.txt
```

**教训**：`git commit --amend` 只改提交信息，不碰文件内容 —— 是安全的修复手段。

### 坑 6：分支合并后忘记打 tag / 删分支

**现象**：Codex 合并了 M1/M2，但 M5/M6 的分支被漏删，一直残留。

**排查**：

```powershell
git branch -v
# feature/m5-cookie-wait    0a08cc6 延长 Cookie 面板等待并保留扫描诊断  ← 已合并却还在
```

**清理**：

```powershell
git branch -d feature/m5-cookie-wait feature/m6-popup-reorder
```

`-d` 只在内容已在 master 时才允许删，是安全检查。若报「not fully merged」（改写历史后常见），先确认内容无丢失再 `-D`。

---

## 5. 备份与找回：三种后悔药

### 药 1：备份分支（本地，不推送）

```powershell
git branch backup/pre-rebase <commit>
```

**特点**：本地可见，`git branch` 列表里会显示。适合「操作前留个本地副本」。

**本项目教训**：这个分支在整理历史时起了作用，但后来因为「master 上已有等价内容」而显得多余，最终用 `-D` 删了。**留之前要想清楚它会不会变成噪音**。

### 药 2：备份 tag（推荐，可推送）

```powershell
git tag -a backup-before-rebase-11.23 <commit> -m "整理历史前的备份..."
```

**特点**：
- 是**不可变的**（不像分支会移动）
- 不会出现在 `git branch` 列表里
- 可以推送到远程，成为**公共后悔药**

**本项目用的就是这个**，远程至今还留着 `backup-before-rebase-11.23`。

### 药 3：reflog（最后的救命稻草）

```powershell
git reflog --date=format:"%m-%d %H:%M"
```

记录 HEAD 和分支指针的每一次移动，**即使提交被 rebase 或 reset 掉，也能找到它当时在哪**。

**找回被 reset 掉的提交**：

```powershell
git reflog
# 找到目标哈希
git reset --hard <哈希>
```

### 药 4：dangling 对象

```powershell
git fsck --lost-found --no-progress
```

改写历史或误删后，**旧对象还在对象库里**，只是不可达。

```powershell
git fsck --lost-found
# 会把对象存到 .git/lost-found/
```

**注意**：执行 `git gc` 之后这些对象会被清理。所以发现历史异常时，**先别 gc**。

### 该用哪个

| 场景 | 用 |
|---|---|
| 操作前留个本地副本 | 备份分支 |
| 需要团队都能回滚 | 备份 tag |
| 「我的改动去哪了」 | reflog |
| 「这个提交还能救吗」 | fsck --lost-found |

---

## 6. 标签策略：本次项目的演进

### 三个阶段的认知

**阶段一（11-23）**：只在改写历史时打了 3 个 tag

```
11.23-initial
11.23-mvp-cleanup
11.23-llm-vision-cleanup
```

打的是**历史节点**，不是每个版本。

**阶段二（11-26）**：M1–M6 六个模块合完，发现没 tag。于是约定「每个模块合并后打一个 tag」。

**阶段三（11-27）**：M7–M9 延续该约定，形成完整序列。

### 现在的约定

```
m1-postal-utils
m2-header-readback
m3-input-readback
m4-delivery-wait
m5-cookie-wait
m6-popup-reorder
m7-es-continue-shopping
m8-roi-ocr-scale
m9-dom-confirmed-unavailable
```

### 命名规则

```
m<序号>-<功能简述>
```

**全部小写、用连字符** —— 跨平台安全，shell 里不用转义。

### annotated vs lightweight

```powershell
git tag -a m9-xxx -m "说明文字"        # annotated（推荐）
git tag m9-xxx                        # lightweight（只是指针）
```

**判断方式**：

```powershell
git for-each-ref --format="%(refname:short) type=%(objecttype)" refs/tags/
# 11.23-initial   type=tag     ← annotated
# m1-postal-utils type=commit  ← lightweight
```

> **注意**：不能用 `git cat-file -t <tag名>` 判断 —— 它会自动解引用到 commit，
> 两种 tag 都返回 `commit`。必须用 `for-each-ref` 的 `%(objecttype)`。

**本项目的实际情况**：早期四个 tag（`11.23-*` 和 `backup-before-rebase-*`）是 annotated，
M1–M9 这批是 lightweight（`git tag mX-xxx` 无 `-m`）。两者都能用，
但 annotated 能带说明文字，lightweight 更轻量。

选择 annotated 的好处：

- 能带说明文字（`git tag -l -n1` 能看到）
- 有独立的哈希，便于单独传输
- 推到远程后 GitHub 能显示说明

### tag 指向合并提交而非分支 tip

```powershell
git merge --no-ff feature/m9-xxx
git tag m9-xxx          # ← 打在这里，此时 HEAD 就是合并提交
```

这样 tag 指向的是**包含该模块的完整历史**，而不是分支上的那个孤立提交。

---

## 7. 推送：PowerShell 环境的可靠做法

### 标准流程

```powershell
git push origin master
git push origin --tags
git status -sb          # 确认后面没有 [ahead N]
```

### 遇到的真实故障：`fatal: helper error (143)`

**现象**：

```
fatal: helper error (143): Unknown
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

**排查过程**：

```powershell
# 1. 凭据管理器本身正常吗？
& "E:/DailyProgram/Aboutcoding/Git/mingw64/bin/git-credential-manager.exe" get @"
protocol=https
host=github.com

"@
# 正常返回 username 和 token

# 2. 读取操作正常吗？
git ls-remote origin refs/heads/master
# 正常

# 3. 结论：写操作路径上的凭据管道坏了
```

**原因**：之前 `taskkill` 杀掉 git 进程时，管道断裂留下了坏状态。

**解决 A**：清掉残留进程后重试

```powershell
Stop-Process -Name git -Force -ErrorAction SilentlyContinue
Stop-Process -Name git-remote-https -Force -ErrorAction SilentlyContinue
git push origin master
```

**解决 B（成功率最高）**：绕过 helper，直接用 token

```powershell
$cred = & "E:/DailyProgram/Aboutcoding/Git/mingw64/bin/git-credential-manager.exe" get @"
protocol=https
host=github.com

"@
$user = ($cred | Select-String '^username=').ToString().Substring(9)
$pass = ($cred | Select-String '^password=').ToString().Substring(9)
git push "https://${user}:${pass}@github.com/WZFrankSun/ai-spider.git" master
git push "https://${user}:${pass}@github.com/WZFrankSun/ai-spider.git" --tags
Remove-Variable cred,user,pass
```

**token 安全**：只存在于 shell 变量，不落盘、不进历史记录。`Remove-Variable` 清理。

### 推送后验证

```powershell
git status -sb
# ## master...origin/master        ← 没有 [ahead N] 就是同步了

git ls-remote origin refs/heads/master
git rev-parse master
# 两个哈希应相同
```

### 端到端验证（推荐）

```powershell
cd $env:TEMP
git clone https://github.com/WZFrankSun/ai-spider.git verify_push
cd verify_push
git log --oneline -3
D:\WZ_Project\ai-spider\.venv\Scripts\python.exe -m unittest discover -s tests
cd ..
Remove-Item -Recurse -Force verify_push
```

**本项目验证结果**：干净克隆后 182 个测试全部通过，13 个 tag 齐全。

---

## 8. 日常命令速查（PowerShell 版）

### 查看状态

```powershell
git status                    # 完整状态
git status -sb                # 简洁（一行，含分支和 ahead/behind）
git log --oneline -10         # 最近 10 条
git log --graph --oneline --decorate   # 带分支图和 tag 标注 ★ 最常用
git log --oneline origin/master..master  # 我领先远程的提交
git diff                      # 工作区 vs 暂存区
git diff --cached             # 暂存区 vs HEAD
git diff --stat               # 只看统计
```

### 分支

```powershell
git branch -v                  # 所有分支及其 tip
git branch --list "feature/*"  # 按模式筛选
git branch feature/mX-xxx     # 创建
git branch -d feature/mX-xxx   # 删除（已合并才允许）
git branch -D feature/mX-xxx   # 强删
git checkout feature/mX-xxx    # 切换
git switch feature/mX-xxx      # 同上（较新写法）
```

### 合并与变基

```powershell
git merge --no-ff feature/mX-xxx    # 合并并保留分支痕迹
git rebase master                   # 把当前分支的提交搬到 master 最新端点
git rebase --continue               # 解决冲突后继续
git rebase --abort                  # 放弃变基
```

### 提交

```powershell
git add <文件>                     # 精确暂存 ★ 优于 git add -A
git add -A                         # 暂存全部（慎用）
git commit -m "信息"
git commit --amend -F <文件>       # 改提交信息，不改内容
git commit --amend --no-edit        # 补文件进上一个提交
```

### tag

```powershell
git tag -l                    # 列出
git tag -l -n1                 # 带说明
git tag -a <名> -m "说明"       # 创建 annotated
git tag -d <名>                # 删除本地
git push origin --tags          # 推送全部 tag
git push origin --delete <名>   # 删除远程 tag
```

### 恢复与排查

```powershell
git reflog                                  # HEAD 移动历史 ★ 排查第一工具
git reflog --date=format:"%m-%d %H:%M"       # 带时间
git fsck --lost-found --no-progress          # 找悬空对象
git show <commit> --stat                    # 看某提交改了什么
git cherry master <branch>                  # 比对等价提交
git rev-parse <commit>^{tree}               # 比对内容树哈希 ★
git cat-file -t <ref>                       # 判断对象类型（tag 会解引用到 commit）
git for-each-ref --format="%(refname:short) %(objecttype)" refs/tags/   # 区分 tag 类型 ★
```

---

## 9. 协作守则

### 本项目确立的规则

**1. 分支职责单一**

一个分支只做一个模块。合并即删除。

**2. 合并前必须 rebase**

```powershell
git checkout feature/mX-xxx
git rebase master
```

否则分支基于过期的 master，后续模块拿不到前面的成果。

**3. 合并用 `--no-ff`**

保留分支痕迹，历史可读。

**4. 每个模块合并后打 tag**

```powershell
git tag mX-<简述>
```

**5. 暂存要精确**

```powershell
git add <本次涉及的文件>
```

提交前用 `git diff --cached --stat` 核对。

**6. 给 AI 的提示词要写明边界**

```
【工作范围】
- 只在当前分支 feature/mX-xxx 上工作
- 完成后提交，但不要切分支、不要 merge、不要删除分支、不要 push
```

**这条是踩过坑才加的**（见坑 1）。

**7. 改写历史前先备份**

```powershell
git tag -a backup-before-<场景> <commit> -m "..."
```

**8. 发现问题先查 reflog**

任何「我的改动去哪了」「这个提交怎么不见了」，先 `git reflog`。

### 关于强推的判断标准

| 情况 | 是否可 force push |
|---|---|
| 只有你一个人用，且已确认内容无丢失 | 可以，但先打 tag |
| 有其他协作者已经拉取 | **不要**，用新提交修正 |
| 团队共享分支 | **不要** |

**更好的替代方案**：不重写历史，直接在旧提交之上加新提交。本项目后来的 M1–M9 全都走这条路。

---

## 附录：本次项目的 Git 时间线

| 时间 | 事件 | 学到的 |
|---|---|---|
| 11-23 17:24 | 首次提交 `41e67bd` | — |
| 11-23 17:31 | 第二次提交 `f771b89`（消息与前者重复） | 提交信息要能区分 |
| 11-23 17:48 | 提交 `aa8b2f7`，清理 LLM 视觉方案依赖 | — |
| 11-23 17:48 | 建 `backup/pre-rebase` 分支 | 操作前留后路 |
| 11-23 17:59 | 用 `commit-tree` 重写历史为三段，`update-ref` 移动 master | plumbing 改写可控 |
| 11-23 18:57 | 提交 `fbb40cd`，恢复配送邮编设置 | — |
| 11-24 15:30 | 提交 `c25fda0`，九站支持 | — |
| 11-26 15:16 | M1 提交 → Codex 自行 merge → 本地 merge 报「分支不存在」 | 提示词要写边界 |
| 11-26 15:23–16:48 | M2–M6 六轮「rebase → 提交 → merge → tag」 | 标准循环成型 |
| 11-26 18:06 | M7 补西班牙站文案 | — |
| 11-27 09:38 | M8 放大 ROI 后 OCR | 先用历史图验证收益再改代码 |
| 11-27 10:32 | M9 判定以 DOM 无按钮为前提 | 先收紧判定再补词库 |
| 11-27 11:0x | push 7 个提交 + 3 个 tag，远程同步 | — |

---

## 一句话总结

> **Git 的核心是「内容寻址 + 可移动指针」。**
> 理解了这一条，其余（为什么 `branch -d` 会拒绝、为什么 reflog 能救命、为什么改写历史需要备份）就都是它的推论。
>
> 而最重要的习惯是：**每一步操作前，先确认「我能不能回来」。**
