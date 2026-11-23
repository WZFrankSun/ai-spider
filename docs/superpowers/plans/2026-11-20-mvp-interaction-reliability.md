# MVP 鎿嶄綔鍙潬鎬?Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 璁?MVP 椤甸潰涓殑鎵弿銆佸鏌ュ拰婕旂ず缁撴灉鎸夐挳涓嶄細閲嶅鎻愪氦鎴栨案涔呭崱浣忥紝骞朵负姣忔鎿嶄綔鎻愪緵鍙悊瑙ｇ殑鍙嶉鍜屾渶杩戞壂鎻忔椂闂淬€?
**Architecture:** 淇濇寔鐜版湁 FastAPI + 鍗曢〉 HTML + 鍐呭瓨 DemoScanner 鏋舵瀯锛屼笉鏂板鍚庣鎺ュ彛銆傛祻瑙堝櫒鑴氭湰澧炲姞鍟嗗搧绾?鍛婅绾ф搷浣滈攣銆佺粺涓€瓒呮椂灏佽鍜?Toast锛涙椂闂翠俊鎭洿鎺ヤ娇鐢ㄧ幇鏈?`/api/scans` 杩斿洖鐨?`started_at`銆乣finished_at`銆?
**Tech Stack:** Python 3.12+銆丗astAPI銆佺幇鏈夊唴鑱?JavaScript銆佹祻瑙堝櫒 `fetch`/`AbortController`銆乣unittest`銆?
**Spec:** `docs/superpowers/specs/2026-11-20-mvp-interaction-reliability-design.md`

## Global Constraints

- MVP 缁х画浣跨敤鍐呭瓨鏁版嵁鍜岀‘瀹氭€?DemoScanner銆?- 鏈疆涓嶆帴鍏ョ湡瀹?Playwright 鎴浘銆丱CR銆並afka銆丮ySQL銆佸畾鏃惰皟搴︽垨鍚庡彴闃熷垪銆?- 鎵弿璇锋眰瓒呮椂鍒濆鍊煎浐瀹氫负 10 绉掋€?- 鎿嶄綔閿佹寜鍟嗗搧鎴栧憡璀︾矑搴︾淮鎶わ紝涓嶉樆濉炲叾浠栧晢鍝佺殑鎿嶄綔銆?- 鍚庣鐜版湁 `409` 骞跺彂淇濇姢蹇呴』淇濈暀骞跺湪鍓嶇杞垚鐢ㄦ埛鍙悊瑙ｇ殑鎻愮ず銆?- 涓嶆柊澧?Python 鎴栧墠绔緷璧栵紝涓嶆敼鍙樼幇鏈変笟鍔＄姸鎬佸惈涔夊拰 API 璺緞銆?- 鏈粡鐢ㄦ埛鎺堟潈涓嶆墽琛?Git commit銆乸ush 鎴栧叾浠栧彂甯冩搷浣滐紱褰撳墠鐩綍涓嶆槸 Git 浠撳簱銆?
## Review Focus

- 鍚屼竴鍟嗗搧蹇€熷弻鍑绘壂鎻忓彧搴斿彂鍑轰竴娆¤姹傦紱鐢?Task 2 鐨勯〉闈氦浜掑绾︽鏌ュ拰鎵嬪姩 smoke 楠岃瘉瑕嗙洊銆?- 涓€涓晢鍝佹壂鎻忔椂鍏朵粬鍟嗗搧浠嶅彲鎿嶄綔锛涚敱 Task 2 鐨勬寜 ID 閿佸疄鐜板拰椤甸潰 smoke 楠岃瘉瑕嗙洊銆?- 璇锋眰瓒呮椂銆佺綉缁滈敊璇拰寮傚父鍝嶅簲閮藉繀椤婚噴鏀炬寜閽紱鐢?Task 2 鐨勮秴鏃跺皝瑁呮鏌ュ拰鎵嬪姩楠岃瘉瑕嗙洊銆?- 鏈嶅姟绔繑鍥?`409` 鏃朵笉鑳芥柊澧炲憡璀︽垨璁╂寜閽案涔呯鐢紱鐢?Task 2 鐨勯敊璇垎鏀鏌ュ拰鐜版湁 API 娴嬭瘯瑕嗙洊銆?- Toast 鍜屾寜閽姸鎬佸繀椤诲悓鏃惰〃杈剧粨鏋滐紝骞舵彁渚涢敭鐩樼劍鐐瑰拰 `aria-live`锛涚敱 Task 1 鐨勯〉闈㈠绾︽祴璇曡鐩栥€?
---

### Task 1: 澧炲姞鏃堕棿璁板綍涓庡弽棣?UI 濂戠害

**Files:**
- Modify: `app/mvp/templates/index.html`锛堣〃鏍煎垪銆乀oast 瀹瑰櫒銆佺姸鎬佹牱寮忓拰鏃犻殰纰嶅睘鎬э級
- Test: `tests/test_mvp_page.py`

**Interfaces:**
- Consumes: `/api/scans` 杩斿洖鐨?`started_at`銆乣finished_at`銆乣status`銆乣error_message`銆?- Produces: `#toast-region`銆乣data-operation`銆佹渶杩戞壂鎻忔椂闂?鑰楁椂鏄剧ず鑺傜偣锛屼緵 Task 2 鐨勮剼鏈洿鏂般€?
- [x] **Step 1: 鍐欓〉闈㈠绾︽祴璇?*

鍦?`MvpPageTests.test_page_contains_state_controls_and_tables` 鎴栫嫭绔嬫祴璇曚腑鏂█椤甸潰鍖呭惈锛?
- `id="toast-region"` 鍜?`aria-live`銆?- `鏈€杩戞壂鎻廯銆乣鑰楁椂`銆乣鏈壂鎻廯 绛夋椂闂磋褰曟枃妗堛€?- `data-operation` 鎴栫瓑浠风殑鎿嶄綔鏍囪瘑銆?- `AbortController`銆乣setTimeout`銆乣finally`銆乣showToast` 绛夎剼鏈绾︺€?- `prefers-reduced-motion` 鍜屽彲瑙佺劍鐐规牱寮忋€?
- [x] **Step 2: 杩愯椤甸潰濂戠害娴嬭瘯纭褰撳墠瀹炵幇缂哄皯濂戠害**

Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_mvp_page -v`

Expected: 鏂板鏂█鍦ㄥ疄鐜板墠澶辫触锛岀幇鏈夐〉闈㈡祴璇曚粛鑳借瀹氫綅鍒板叿浣撶己澶辨爣璁般€?
- [x] **Step 3: 鍦ㄦā鏉夸腑鍔犲叆鏃堕棿璁板綍鍜?Toast 瀹瑰櫒**

澧炲姞鏈€杩戞壂鎻忓垪锛屽睍绀猴細鏃犳壂鎻忔椂 `鏈壂鎻廯锛涙湁鎵弿鏃跺睍绀哄畬鎴愭椂闂村拰鑰楁椂锛涙壂鎻忚繘琛屼腑灞曠ず寮€濮嬫椂闂淬€傚鍔犱竴涓浐瀹氫絾涓嶉伄鎸℃搷浣滆鐨?`#toast-region`锛屾秷鎭娇鐢?`role="status"` 鎴?`role="alert"`銆?
- [x] **Step 4: 澧炲姞鐘舵€佹牱寮忎笌鍙闂€ф牱寮?*

涓哄鐞嗕腑銆佹垚鍔熴€佸け璐ュ拰鍙噸璇曟寜閽繚鐣欐枃瀛楃姸鎬侊紝鍚屾椂鎻愪緵 `:focus-visible` 鐒︾偣鏍峰紡銆乣aria-busy`/`aria-disabled` 灞炴€у拰 `prefers-reduced-motion` 闄嶇骇瑙勫垯銆備笉瑕佸紩鍏ユ柊鐨?CSS 妗嗘灦鎴栧姩鐢诲簱銆?
- [x] **Step 5: 杩愯椤甸潰濂戠害娴嬭瘯纭閫氳繃**

Run: `uv run --cache-dir .uv-cache python -m unittest tests.test_mvp_page -v`

Expected: PASS銆?
### Task 2: 瀹炵幇鎿嶄綔閿併€佽秴鏃舵仮澶嶅拰娑堟伅鍙嶉

**Files:**
- Modify: `app/mvp/templates/index.html`锛堢幇鏈夊唴鑱旇剼鏈級
- Test: `tests/test_mvp_page.py`銆佺幇鏈?`tests/test_monitoring_api.py`

**Interfaces:**
- Consumes: Task 1 鐨?`#toast-region`銆佹搷浣滄爣璇嗗拰鐜版湁 API銆?- Produces: `showToast(message, kind)`銆乣requestJson(url, options, timeoutMs = 10000)`銆佹寜鎿嶄綔 ID 鐨勯攣瀹?閲婃斁閫昏緫锛屼緵鎵弿銆佸鏌ュ拰婕旂ず缁撴灉璁剧疆鍏辩敤銆?
- [x] **Step 1: 涓?`requestJson` 瀹氫箟澶辫触鍒嗙被**

璁╄姹傚皝瑁呬娇鐢?`AbortController` 鍜?10 绉掕鏃跺櫒锛涘尯鍒嗚秴鏃躲€佺綉缁滈敊璇€乣409` 鍜屽叾浠?HTTP 閿欒銆傝В鏋愰敊璇搷搴旀椂浼樺厛浣跨敤鍚庣 `detail`锛屾病鏈?detail 鏃朵娇鐢ㄧ姸鎬佹枃鏈€?
- [x] **Step 2: 瀹炵幇 `showToast(message, kind)`**

澶嶇敤鍗曚竴 Toast 瀹瑰櫒锛岃缃垚鍔熴€佷俊鎭€佽鍛娿€侀敊璇洓绉嶆牱寮忥紱姣忔潯娑堟伅鑷姩娑堝け锛屽苟鍏佽鐢ㄦ埛鎵嬪姩鍏抽棴銆傞敊璇娇鐢?`role="alert"`锛屽叾浠栨秷鎭娇鐢?`role="status"`銆?
- [x] **Step 3: 瀹炵幇鎸?ID 鐨勬搷浣滈攣**

浣跨敤 `Set` 鎴栫瓑浠风粨鏋勭淮鎶?`scan:{productId}`銆乣verify:{alertId}`銆乣demo-result:{productId}`銆傜偣鍑诲墠妫€鏌ラ攣锛岀偣鍑诲悗绔嬪嵆璁剧疆鎸夐挳鏂囨鍜?`disabled`/`aria-busy`锛屽湪 `finally` 涓敮涓€閲婃斁閿併€?
- [x] **Step 4: 鎺ュ叆鎵弿銆佸鏌ュ拰婕旂ず缁撴灉鎸夐挳**

鎵弿鎸夐挳鏄剧ず鈥滄壂鎻忎腑鈥︹€濆苟鍦ㄦ垚鍔熷悗鍒锋柊鏁版嵁锛涘簱瀛橀闄┿€佹妧鏈晠闅滃拰鎴愬姛缁撴灉鍒嗗埆鏄剧ず瀵瑰簲 Toast銆俙409` 鏄剧ず鈥滆鍟嗗搧姝ｅ湪鎵弿锛岃绋嶅€欌€濆苟鍒锋柊鏁版嵁銆傚鏌ユ寜閽樉绀衡€滈獙璇佷腑鈥︹€濓紱婕旂ず缁撴灉璁剧疆鎸夐挳鏄剧ず鈥滃凡璁剧疆涓嬩竴娆＄粨鏋溾€濄€傚け璐ユ垨瓒呮椂缁熶竴鎭㈠涓哄彲閲嶈瘯鐘舵€併€?
- [x] **Step 5: 纭繚鏃堕棿璁板綍鍦ㄦ瘡娆″埛鏂板悗鏇存柊**

浠庢渶鏂版壂鎻忚褰曟牸寮忓寲 ISO 鏃堕棿锛岃绠?`finished_at - started_at` 鐨勭鏁帮紱鎵弿涓彧鏄剧ず寮€濮嬫椂闂达紝瀹屾垚鍚庢樉绀哄畬鎴愭椂闂村拰鑰楁椂锛屾妧鏈晠闅滃悓鏃舵樉绀洪敊璇師鍥犮€?
- [x] **Step 6: 杩愯鐜版湁 API 鍜岄〉闈㈡祴璇?*

Run: `uv run --cache-dir .uv-cache python -m unittest discover -s tests -p "test_*.py" -v`

Expected: 鍏ㄩ儴鐜版湁娴嬭瘯閫氳繃锛涘仴搴锋鏌ヤ粛杩斿洖 `{"status":"ok","mode":"demo"}`銆?
### Task 3: 鍋氭渶灏忔祻瑙堝櫒绾ч獙鏀?
**Files:**
- Test/Manual: `app/mvp/templates/index.html`銆乣app.py`

**Interfaces:**
- Consumes: Task 1 鍜?Task 2 鐨勯〉闈氦浜掋€?- Produces: 鍙噸澶嶆墽琛岀殑鏈湴楠屾敹姝ラ锛屼笉澧炲姞鑷姩鍖栨祴璇曚緷璧栥€?
- [x] **Step 1: 鍚姩 MVP 鏈嶅姟**

Run:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run python app.py
```

- [x] **Step 2: 楠岃瘉閲嶅鐐瑰嚮鍜屽苟琛屽晢鍝佹搷浣?*

鎵撳紑 `http://127.0.0.1:8000`锛岃繛缁揩閫熺偣鍑诲悓涓€鍟嗗搧鐨勨€滅珛鍗虫壂鎻忊€濓紝纭鍙繘鍏ヤ竴娆″鐞嗕腑锛涙壂鎻忓彟涓€涓晢鍝佹椂纭鍏舵寜閽粛鍙搷浣溿€?
- [x] **Step 3: 楠岃瘉鍙嶉鍜屾仮澶?*

鍒嗗埆婕旂ず鍋ュ悍銆佸簱瀛樺紓甯搞€佹妧鏈晠闅溿€佸鏌ュ拰閲嶅璇锋眰锛岀‘璁?Toast銆佹寜閽枃妗堛€佹渶杩戞壂鎻忔椂闂村拰鑰楁椂涓€鑷达紱缃戠粶澶辫触鎴栬秴鏃跺悗鎸夐挳蹇呴』鍙互閲嶈瘯銆?
- [x] **Step 4: 鍋滄鏈嶅姟骞惰褰曠粨鏋?*

浣跨敤 `Ctrl+C` 鍋滄鏈嶅姟锛岃褰曢〉闈㈤獙鏀剁粨鏋滐紱涓嶆墽琛屾彁浜ゆ垨鍙戝竷銆?
## 瀹屾垚鏍囧噯

- 鍚屼竴鎿嶄綔鐨勯噸澶嶇偣鍑讳笉浼氬彂鍑洪噸澶嶈姹傘€?- 浠绘剰璇锋眰璺緞閮戒細鍦ㄦ垚鍔熴€佸け璐ャ€乣409` 鎴栬秴鏃跺悗閲婃斁鎸夐挳銆?- 鐢ㄦ埛鑳界湅鍒版槑纭殑娑堟伅鍙嶉銆佹渶杩戞壂鎻忔椂闂村拰鑰楁椂銆?- 鐜版湁 35 涓祴璇曠户缁€氳繃锛孧VP 鍋ュ悍妫€鏌ヤ繚鎸?demo 妯″紡銆?- 椤甸潰涓嶅姞杞?Kafka銆佺湡瀹炴壂鎻忔垨鍏朵粬 MVP 涔嬪鐨勭敓浜ч摼璺€?
