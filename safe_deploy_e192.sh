#!/bin/bash
# ============================================================================
# safe_deploy_e192.sh — استقرار ایمن برای شاخهٔ سرور
#   شاخهٔ هدف : arena/01a0e192-agent-auto-post-bot
#
# این اسکریپت:
#   1. Preflight: بررسی شاخه، وضعیت محلی، و اینکه تغییرات ورودی دقیقاً چه
#      فایل‌هایی را عوض می‌کنند. اگر هر فایل تغییر‌کردهٔ محلی با فایل‌های
#      ورودی برهم‌بخورند → توقف (بدون هیچ‌گونه overwrite).
#   2. Backup: بکاپ SQLite-compatible از auth.db (hot backup قبل از توقف،
#      cold backup بعد از توقف)، کپی config.json (بدون چاپ محتوا)، users/،
#      و جلسات واتساپ (whatsapp-service/auth) + مانیفست وضعیت.
#   3. فقط ربات Bale را متوقف می‌کند (PID تاییدشده از bot.pid).
#      هیچ‌گاه WhatsApp، پورت 3001، neonize_service یا whatsapp.pid را
#      لمس نمی‌کند.
#   4. آپدیت فقط با `git fetch` + `git merge --ff-only`.
#      بدون reset --hard، بدون git clean، بدون checkout، بدون rm -rf.
#   5. فقط bot.py را دوباره start می‌کند (مثل start.sh ولی بدون بخش
#      واتساپ) و در پایان همهٔ داده‌ها را verify می‌کند.
#
# استفاده:
#   ./safe_deploy_e192.sh --dry-run   # فقط بررسی؛ هیچ چیزی تغییر نمی‌کند
#   ./safe_deploy_e192.sh             # preflight + backup + deploy + verify
#
# اجرا از بیرون رپو (برای اولین deploy که اسکریپت هنوز روی سرور نیست):
#   DEPLOY_DIR=/path/to/repo bash /tmp/safe_deploy_e192.sh --dry-run
#   DEPLOY_DIR=/path/to/repo bash /tmp/safe_deploy_e192.sh
#   (DEPLOY_DIR مسیر ریشهٔ رپو است؛ خود deploy اسکریپت را در رپو ثبت می‌کند)
#
# ابزارها: فقط bash، git، grep، sed، tar، curl، python3 (نه ripgrep).
# ============================================================================
set -u

EXPECTED_BRANCH="arena/01a0e192-agent-auto-post-bot"
REMOTE="${DEPLOY_REMOTE:-origin}"
PYTHON_BIN="${DEPLOY_PYTHON:-python3}"
MASSENGER="all_pg_agnet/AGENT-MANAGER_BOTS_MASSENGER"

md5of() {
    if command -v md5sum >/dev/null 2>&1; then
        md5sum "$1" 2>/dev/null | sed 's/ .*//'
    else
        python3 -c "import hashlib,sys; print(hashlib.md5(open(sys.argv[1],'rb').read()).hexdigest())" "$1" 2>/dev/null
    fi
}
DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; fi

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
say()  { echo -e "${BLUE}$*${NC}"; }
ok()   { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
die()  { echo -e "${RED}⛔ $*${NC}"; echo -e "${RED}   deploy لغو شد؛ هیچ تغییری اعمال نشد.${NC}"; exit 1; }

# ---------- مرحله 0: sanity ----------
say "🔎 Preflight — مرحله 0: sanity"
SCRIPT_DIR="${DEPLOY_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$SCRIPT_DIR" || die "نمی‌توان به پوشهٔ رپو رفت: $SCRIPT_DIR"
git rev-parse --git-dir >/dev/null 2>&1 || die "این یک git repository نیست: $SCRIPT_DIR"
command -v git >/dev/null     || die "git پیدا نشد"
command -v python3 >/dev/null || die "python3 پیدا نشد"

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
if [ "$BRANCH" != "$EXPECTED_BRANCH" ]; then
    die "شاخهٔ فعلی «$BRANCH» است، ولی این اسکریپت فقط روی «$EXPECTED_BRANCH» اجرا می‌شود. (هیچ switch‌ی خودکار انجام نمی‌دهیم)"
fi
HEAD_SHA="$(git rev-parse HEAD)"
ok "شاخه: $BRANCH @ $HEAD_SHA"

# ---------- وضعیت پیشین (برای verify در انتها) ----------
WA_PID=""
if [ -f "whatsapp-service/whatsapp.pid" ]; then WA_PID="$(tr -d '[:space:]' < whatsapp-service/whatsapp.pid)"; fi
BOT_PID=""
if [ -f "$MASSENGER/bot.pid" ]; then BOT_PID="$(tr -d '[:space:]' < "$MASSENGER/bot.pid")"; fi
WA_OK=0; curl -s --max-time 5 http://localhost:3001/ 2>/dev/null | grep -q "ok" && WA_OK=1
CFG_MD5_BEFORE=""
[ -f "$MASSENGER/config.json" ] && CFG_MD5_BEFORE="$(md5of "$MASSENGER/config.json")"
USERS_COUNT_BEFORE=0
[ -d "$MASSENGER/users" ] && USERS_COUNT_BEFORE="$(find "$MASSENGER/users" -type f 2>/dev/null | wc -l)"
WA_AUTH_COUNT_BEFORE=0
[ -d "whatsapp-service/auth" ] && WA_AUTH_COUNT_BEFORE="$(find whatsapp-service/auth -type f 2>/dev/null | wc -l)"
DB_USERS_BEFORE=""
if [ -f "$MASSENGER/auth.db" ]; then
    DB_USERS_BEFORE="$(python3 - "$MASSENGER/auth.db" <<'PYEOF' 2>/dev/null || echo "read-failed"
import sqlite3, sys
c = sqlite3.connect(sys.argv[1], timeout=10)
print(c.execute("SELECT count(*) FROM users").fetchone()[0])
c.close()
PYEOF
)"
fi
echo "   وضعیت فعلی: WhatsApp PID=${WA_PID:-none} ${WA_OK:+(روشن)} | Bale PID=${BOT_PID:-none}"
echo "   config.json: ${CFG_MD5_BEFORE:-exists?} | users: $USERS_COUNT_BEFORE فایل | واتساپ-auth: $WA_AUTH_COUNT_BEFORE فایل | auth.db users: ${DB_USERS_BEFORE:-none}"

# ---------- تغییرات محلی (فقط خواندنی) ----------
LOCAL_DIRTY="$(git status --porcelain | sed -n 's/^..//p' | tr '\n' ' ')"
COMING_FILES=""
if git fetch "$REMOTE" "$EXPECTED_BRANCH" --quiet 2>/dev/null; then
    REMOTE_TIP="$(git rev-parse "$REMOTE/$EXPECTED_BRANCH" 2>/dev/null || echo "")"
    ok "fetch شد؛ نوک شاخهٔ $REMOTE: ${REMOTE_TIP:0:12}"
    if [ -n "$REMOTE_TIP" ] && [ "$REMOTE_TIP" != "$HEAD_SHA" ]; then
        git merge-base --is-ancestor HEAD "$REMOTE/$EXPECTED_BRANCH" 2>/dev/null \
            || die "تغییرات سرور روی $REMOTE/$EXPECTED_BRANCH fast-forward نیست. توقف شد — اول تفاوت‌ها را بررسی کن (حدس نمی‌زنیم)"
        COMING_FILES="$(git diff --name-only HEAD "$REMOTE/$EXPECTED_BRANCH")"
        echo "   فایل‌هایی که deploy عوض می‌کند:"
        sed 's/^/     - /' <<< "$COMING_FILES"
    else
        COMING_FILES=""
    fi
else
    warn "fetch از $REMOTE شکست خورد (اینترنت/آدرس). deploy بدون fetch ممکن نیست → توقف"
    exit 1
fi

# برخورد تغییرات محلی با فایل‌های ورودی؟
CONFLICT_FILES=""
for f in $COMING_FILES; do
    case " $LOCAL_DIRTY " in *" $f "*) CONFLICT_FILES="$CONFLICT_FILES $f";; esac
done
if [ -n "$CONFLICT_FILES" ]; then
    die "این فایل‌ها هم روی سرور تغییر محلی دارند و هم در تغییرات ورودی هستند:$CONFLICT_FILES
   deploy متوقف شد. اول وضعیت این فایل‌ها را بررسی کن (نه با reset/clean). این اسکریپت هیچ‌کدام را overwrite نمی‌کند."
fi

# آیا تغییرات PR #5 در شاخهٔ ریموت هست؟
if [ -n "$COMING_FILES" ]; then
    if git log --oneline HEAD.."$REMOTE/$EXPECTED_BRANCH" 2>/dev/null | grep -q "reconcile PR #5"; then
        ok "تغییرات سازگارشدهٔ PR #5 در شاخهٔ $REMOTE هست"
    else
        warn "commit «reconcile PR #5» در HEAD..$REMOTE/$EXPECTED_BRANCH پیدا نشد — مطمئن شو PR مربوطه ادغام شده"
    fi
else
    say "📭 هیچ تغییر جدیدی روی $REMOTE/$EXPECTED_BRANCH وجود ندارد (سرور به‌روز است یا PR هنوز ادغام نشده)"
    [ "$DRY_RUN" = "1" ] && { echo -e "${YELLOW}   dry-run: اینجا تمام می‌شود — کار دیگری لازم نیست.${NC}"; exit 0; }
    die "چیزی برای deploy وجود ندارد"
fi

# ---------- dry-run: همین‌جا پایان ----------
if [ "$DRY_RUN" = "1" ]; then
    echo ""
    say "🧪 DRY-RUN — plan عملیات (هیچ‌کدام اجرا نشد):"
    echo "   1) backup → backups/deploy-<ts>/ : sqlite .backup از $MASSENGER/auth.db (hot)،"
    echo "      کپی config.json، tar از users/ و whatsapp-service/auth، مانیفست"
    echo "   2) توقف فقط Bale Bot (PID از $MASSENGER/bot.pid، تایید شده از /proc) — WhatsApp دست‌نخورده"
    echo "   3) backup دوم auth.db (cold) + integrity_check"
    echo "   4) git merge --ff-only $REMOTE/$EXPECTED_BRANCH  (فقط این فایل‌ها:)"
    for cf in $COMING_FILES; do echo "        - $cf"; done
    echo "   5) start فقط bot.py (nohup) + نوشتن bot.pid"
    echo "   6) verify: WhatsApp همان PID روشن، users/config/واتساپ-auth دست‌نخورده، py_compile"
    echo -e "${GREEN}✅ dry-run موفق — همهٔ preflight‌ها عبور کردند. برای اجرای واقعی: ./safe_deploy_e192.sh${NC}"
    exit 0
fi

# ---------- مرحله 1: backup ----------
say "📦 Backup — مرحله 1"
TS="$(date +%Y%m%d-%H%M%S)"
BK="backups/deploy-$TS"
mkdir -p "$BK" || die "ساخت $BK ناموفق بود"

if [ -f "$MASSENGER/auth.db" ]; then
    python3 - "$MASSENGER/auth.db" "$BK/auth.db.hot" <<'PYEOF' || die "hot backup از auth.db ناموفق بود — توقف قبل از هر تغییری"
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
with src:
    src.backup(dst)
src.close(); dst.close()
c = sqlite3.connect(sys.argv[2])
integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
users = c.execute("SELECT count(*) FROM users").fetchone()[0]
c.close()
assert integrity == "ok", f"integrity: {integrity}"
print(f"users={users} integrity={integrity}")
PYEOF
    ok "auth.db → $BK/auth.db.hot (hot backup، integrity ok)"
else
    warn "auth.db وجود ندارد — deploy بدون دیتابیس (نصب تازه)"
fi
if [ -n "$CFG_MD5_BEFORE" ]; then
    cp "$MASSENGER/config.json" "$BK/config.json" || die "کپی config.json ناموفق بود"
    ok "config.json → $BK/config.json (محتوا چاپ نشد)"
fi
if [ -d "$MASSENGER/users" ] && [ "$USERS_COUNT_BEFORE" -gt 0 ]; then
    tar -cf "$BK/users.tar" -C "$MASSENGER" users || die "بکاپ users/ ناموفق بود"
    ok "users/ → $BK/users.tar ($USERS_COUNT_BEFORE فایل)"
fi
if [ -d "whatsapp-service/auth" ] && [ "$WA_AUTH_COUNT_BEFORE" -gt 0 ]; then
    tar -cf "$BK/whatsapp-auth.tar" -C whatsapp-service auth || die "بکاپ جلسات واتساپ ناموفق بود"
    ok "whatsapp-service/auth → $BK/whatsapp-auth.tar ($WA_AUTH_COUNT_BEFORE فایل)"
fi
{
    echo "deploy time      : $(date -Is 2>/dev/null || date)"
    echo "repo dir         : $SCRIPT_DIR"
    echo "branch           : $BRANCH"
    echo "head before      : $HEAD_SHA"
    echo "remote tip after : ${REMOTE_TIP:-n/a}"
    echo "incoming files   : $(echo ${COMING_FILES:-none})"
    echo "local dirty      : $(echo ${LOCAL_DIRTY:-clean})"
    echo "whatsapp pid     : ${WA_PID:-none}"
    echo "bot pid          : ${BOT_PID:-none}"
    echo "config md5       : $CFG_MD5_BEFORE"
    echo "users files      : $USERS_COUNT_BEFORE"
    echo "wa auth files    : $WA_AUTH_COUNT_BEFORE"
    echo "db users         : $DB_USERS_BEFORE"
} > "$BK/manifest.txt"
ok "مانیفست → $BK/manifest.txt"

# ---------- مرحله 2: توقف فقط Bale Bot ----------
say "🛑 توقف ربات Bale (فقط) — مرحله 2"
if [ -n "$BOT_PID" ] && kill -0 "$BOT_PID" 2>/dev/null; then
    CMDLINE="$(tr '\0' ' ' < "/proc/$BOT_PID/cmdline" 2>/dev/null || echo "")"
    case "$CMDLINE" in
        *bot.py*)
            kill -TERM "$BOT_PID" 2>/dev/null
            i=0
            while kill -0 "$BOT_PID" 2>/dev/null && [ $i -lt 15 ]; do sleep 1; i=$((i+1)); done
            if kill -0 "$BOT_PID" 2>/dev/null; then
                CMDLINE2="$(tr '\0' ' ' < "/proc/$BOT_PID/cmdline" 2>/dev/null || echo "")"
                case "$CMDLINE2" in *bot.py*) kill -KILL "$BOT_PID" 2>/dev/null; sleep 1;; esac
            fi
            if kill -0 "$BOT_PID" 2>/dev/null; then die "توقف PID $BOT_PID ناموفق بود — ادامه نمی‌دهیم"; fi
            ok "Bale Bot (PID $BOT_PID) متوقف شد"
            ;;
        *)
            warn "PID $BOT_PID (cmdline: ${CMDLINE:-?}) با bot.py مطابقت ندارد — اصلاً kill نمی‌کنیم"
            ;;
    esac
else
    [ -n "$BOT_PID" ] && ok "Bale Bot از قبل خاموش بود (PID $BOT_PID مرده)" || warn "bot.pid موجود نیست (ربات خاموش است؟)"
fi
# sanity: واتساپ باید دست‌نخورده باشد
if [ -n "$WA_PID" ] && ! kill -0 "$WA_PID" 2>/dev/null; then
    die "PID واتساپ ($WA_PID) دیگر زنده نیست — این اسکریپت واتساپ را لمس نکرده؛ وضعیت را قبل از ادامه بررسی کن"
fi
ok "WhatsApp دست‌نخورده است (PID ${WA_PID:-none})"

# ---------- مرحله 3: cold backup + integrity ----------
say "💾 Cold backup دیتابیس — مرحله 3"
if [ -f "$MASSENGER/auth.db" ]; then
    python3 - "$MASSENGER/auth.db" "$BK/auth.db" <<'PYEOF' || die "cold backup از auth.db ناموفق بود"
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
with src:
    src.backup(dst)
src.close(); dst.close()
c = sqlite3.connect(sys.argv[2])
users = c.execute("SELECT count(*) FROM users").fetchone()[0]
integrity = c.execute("PRAGMA integrity_check").fetchone()[0]
c.close()
assert integrity == "ok", f"integrity: {integrity}"
print(f"users={users} integrity={integrity}")
PYEOF
    ok "auth.db → $BK/auth.db (cold backup، integrity ok)"
fi

# ---------- مرحله 4: آپدیت fast-forward ----------
say "🔀 آپدیت — مرحله 4 (git merge --ff-only)"
git merge --ff-only "$REMOTE/$EXPECTED_BRANCH" || die "git merge --ff-only شکست خورد — وضعیت بدون تغییر باقی ماند؛ بکاپ‌ها در $BK"
ok "به‌روزرسانی تا $(git rev-parse --short HEAD) انجام شد"
AFTER_DIRTY="$(git status --porcelain | sed -n 's/^..//p' | tr '\n' ' ')"
for f in $COMING_FILES; do
    case " $AFTER_DIRTY " in *" $f "*) die "فایل $f بعد از merge dirty است?! بررسی کن ($BK)";; esac
done

# ---------- مرحله 5: start فقط Bale Bot ----------
say "🚀 اجرای ربات Bale (فقط) — مرحله 5"
cd "$MASSENGER" || die "پیدا نشد: $MASSENGER"
if [ -f "auth.db" ]; then
    DB_OK=0
    for i in 1 2 3 4 5; do
        if python3 -c "import sqlite3; c=sqlite3.connect('auth.db', timeout=10); c.execute('SELECT count(*) FROM users').fetchone(); c.close()" 2>/dev/null; then DB_OK=1; break; fi
        warn "auth.db قفل/مشغول است، تلاش مجدد ($i/5)..."
        sleep 2
    done
    [ "$DB_OK" = "1" ] || die "auth.db قابل خواندن نیست — استارت متوقف شد تا دیتابیس آسیب نبیند (بکاپ: $BK)"
    ok "auth.db سالم است — حفظ شد"
fi
mkdir -p users
rm -f bot.pid
nohup "$PYTHON_BIN" bot.py > bot.log 2>&1 &
NEW_BOT_PID=$!
echo "$NEW_BOT_PID" > bot.pid
cd "$SCRIPT_DIR"
sleep 3
if kill -0 "$NEW_BOT_PID" 2>/dev/null; then
    ok "Bale Bot اجرا شد PID: $NEW_BOT_PID"
else
    echo -e "${RED}⛔ bot.py پس از start مرد — بررسی کن: $MASSENGER/bot.log${NC}"
    sed -n '1,15p' "$MASSENGER/bot.log" 2>/dev/null | sed 's/^/     | /'
    echo -e "${YELLOW}وضعیت فعلی: کد جدید روی شاخه اعمال شده است، ولی ربات اجرا نمی‌شود.${NC}"
    echo -e "${YELLOW}   بکاپ کامل (شامل config.json و auth.db قبل از deploy): $BK${NC}"
    echo -e "${YELLOW}   اگر علت، config.json است: مقایسه $MASSENGER/config.json با $BK/config.json و اصلاح دستی.${NC}"
    echo -e "${YELLOW}   rollback دستی (فقط با تصمیم خودت، اسکریپت هیچ‌چیز را خودکار revert نمی‌کند):${NC}"
    echo -e "${YELLOW}     git reset --hard $HEAD_SHA (بعد از بررسی کامل دلیل خرابی)${NC}"
    exit 1
fi

# ---------- مرحله 6: verify ----------
say "🔍 Verify — مرحله 6"
FAIL=0
# 6.1 WhatsApp همان PID قبل
if [ -n "$WA_PID" ]; then
    if kill -0 "$WA_PID" 2>/dev/null; then ok "WhatsApp همان PID قبل ($WA_PID) — قطع نشد"; else FAIL=1; warn "PID واتساپ پیدا نشد!"; fi
fi
curl -s --max-time 5 http://localhost:3001/ 2>/dev/null | grep -q "ok" && ok "WhatsApp http://localhost:3001 = ok" || { FAIL=1; warn "واکنش localhost:3001 دریافت نشد"; }
# 6.2 Bale زنده
kill -0 "$NEW_BOT_PID" 2>/dev/null && ok "Bale Bot زنده (PID $NEW_BOT_PID)" || { FAIL=1; warn "Bale Bot زنده نیست!"; }
# 6.3 داده‌ها دست‌نخورده
CFG_MD5_AFTER="$(md5of "$MASSENGER/config.json")"
if [ -n "$CFG_MD5_BEFORE" ]; then
    [ "$CFG_MD5_BEFORE" = "$CFG_MD5_AFTER" ] && ok "config.json دست‌نخورده (md5 هم‌خوان)" || { FAIL=1; warn "md5 config.json تغییر کرد!"; }
fi
USERS_COUNT_AFTER="$(find "$MASSENGER/users" -type f 2>/dev/null | wc -l)"
[ "$USERS_COUNT_BEFORE" = "$USERS_COUNT_AFTER" ] && ok "users/ دست‌نخورده ($USERS_COUNT_AFTER فایل)" || { FAIL=1; warn "تعداد فایل users/ تغییر کرد!"; }
WA_AUTH_COUNT_AFTER="$(find whatsapp-service/auth -type f 2>/dev/null | wc -l)"
[ "$WA_AUTH_COUNT_BEFORE" = "$WA_AUTH_COUNT_AFTER" ] && ok "جلسات واتساپ دست‌نخورده ($WA_AUTH_COUNT_AFTER فایل)" || { FAIL=1; warn "تعداد فایل‌های auth واتساپ تغییر کرد!"; }
DB_USERS_AFTER=""
if [ -f "$MASSENGER/auth.db" ]; then
    i=0
    while [ $i -lt 3 ]; do
        DB_USERS_AFTER="$(python3 -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1], timeout=10); print(c.execute('SELECT count(*) FROM users').fetchone()[0]); c.close()" "$MASSENGER/auth.db" 2>/dev/null || true)"
        [ -n "$DB_USERS_AFTER" ] && break
        sleep 2; i=$((i+1))
    done
fi
if [ -n "$DB_USERS_BEFORE" ] && [ "$DB_USERS_BEFORE" != "read-failed" ]; then
    if [ -n "$DB_USERS_AFTER" ]; then
        [ "$DB_USERS_BEFORE" = "$DB_USERS_AFTER" ] && ok "auth.db: تعداد users ثابت ($DB_USERS_AFTER)" || { FAIL=1; warn "تعداد users در auth.db تغییر کرد! (قبل: $DB_USERS_BEFORE / بعد: $DB_USERS_AFTER)"; }
    else
        warn "خواندن auth.db برای verify ممکن نبود (احتمالاً قفل موقت) — دستی بررسی کن: SELECT count(*) FROM users"
    fi
fi
# 6.4 py_compile (همان روال سرور)
python3 -m py_compile "$MASSENGER/bot.py" "$MASSENGER/logger.py" 2>/dev/null && ok "py_compile bot.py + logger.py" || { FAIL=1; warn "py_compile شکست خورد!"; }
# 6.5 خطای ابتدایی در لاگ؟
sleep 2
if grep -q "Traceback" "$MASSENGER/bot.log" 2>/dev/null; then
    warn "Traceback در ابتدای bot.log دیده شد — بررسی کن:"
    sed -n '1,15p' "$MASSENGER/bot.log"
fi

echo ""
if [ "$FAIL" = "0" ]; then
    ok "🎉 deploy با موفقیت انجام شد"
else
    warn "deploy انجام شد ولی بعضی verify‌ها مشکوک بود — وضعیت را بررسی کن"
fi
echo "   شاخه: $BRANCH @ $(git rev-parse --short HEAD)"
echo "   بکاپ: $BK (auth.db + config.json + users + واتساپ-auth + مانیفست)"
echo "   وضعیت: ./status.sh"
exit $FAIL
