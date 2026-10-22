# نصب‌کننده‌ی most-racist-rice-V2 برای CachyOS

اسکریپت پایتون برای نصب خودکار رایس [most-racist-rice-V2](https://github.com/Zeibytes/most-racist-rice-V2) روی **CachyOS / Arch Linux**.

## اجرا

```bash
python install_rice.py
```

> ⚠️ اسکریپت را با **یوزر معمولی** اجرا کنید، نه با `sudo` — خودش هر جا لازم باشد از sudo استفاده می‌کند.

## مراحل کار اسکریپت

1. **کلون کردن ریپو** از گیت‌هاب (یا استفاده از کپی محلی با `--local-repo`)
2. **نصب پکیج‌ها** با pacman — فقط پکیج‌های نصب‌نشده
3. **بکاپ گرفتن** از هر فولدر `~/.config` و هر فونتی که قرار است تغییر کند → در `~/rice-backups/backup-<timestamp>/`
4. **کپی کردن کانفیگ‌ها** در `~/.config` و **اصلاح خودکار مسیرهای هاردکد شده‌ی `/home/zei`** به home شما
5. **نصب فونت‌های Waycat و Skulltype** در `~/.local/share/fonts` + اجرایی کردن اسکریپت‌های waybar
6. **سینک کردن پلاگین‌های LazyVim** به‌صورت headless

## پکیج‌هایی که نصب می‌شوند

| دسته | پکیج‌ها |
|---|---|
| کامپوزیتور / سشن | `hyprland` `hyprlock` `mangowm` `xdg-desktop-portal-hyprland` `qt6-wayland` |
| ترمینال / شل | `kitty` `fish` |
| لانچر | `fuzzel` `rofi-wayland` |
| نوار وضعیت | `waybar` `bc` `wireplumber` `pavucontrol` |
| والپیپر / اسکرین‌شات | `swaybg` `grim` `slurp` `satty` |
| کلیدهای مدیا | `pamixer` `playerctl` |
| Neovim (LazyVim) | `neovim` `git` `base-devel` `curl` `wget` `unzip` `gzip` `ripgrep` `fd` `lazygit` `nodejs` `npm` `python-pip` |
| سایر | `fastfetch` `dolphin` `openrgb` |
| تم / آیکون / فونت | `breeze-gtk` `adwaita-icon-theme` `adwaita-fonts` `ttf-jetbrains-mono-nerd` |
| اختیاری (رسمی) | `librewolf` `flameshot` — با `--with-optional` |
| اختیاری (AUR) | `spotify` — با `--with-aur` (نیاز به paru/yay) |

## فلگ‌ها

```
--dry-run            فقط نشان می‌دهد چه کارهایی انجام می‌شود (بدون تغییر)
-y, --yes            بدون سؤال (فقط پکیج‌های اصلی)
--skip-packages      مرحله‌ی نصب پکیج رد شود (فقط بکاپ + کپی)
--with-optional      نصب librewolf و flameshot هم
--with-aur           نصب spotify از AUR هم
--skip-optional      اصلاً درباره‌ی پکیج‌های اختیاری سؤال نکند
--no-nvim-plugins    سینک پلاگین‌های LazyVim اجرا نشود
--local-repo PATH    به‌جای کلون کردن، از کپی محلی ریپو استفاده کن
--restore            لیست بکاپ‌ها را نشان می‌دهد
--restore latest     بازگردانی به آخرین بکاپ (رول‌بک کامل)
```

## بازگردانی (Undo)

```bash
python install_rice.py --restore           # لیست بکاپ‌ها
python install_rice.py --restore latest    # برگرداندن آخرین بکاپ
```

بکاپ‌ها در `~/rice-backups/` با ساختار آینه‌ای home ذخیره می‌شوند.

## بعد از نصب

1. لاگ‌اوت کنید و در SDDM سشن **Hyprland** (یا **mango**) را انتخاب کنید.
2. در `~/.config/hypr/hyprland.lua` حالت مانیتور `1920x1080@144hz` هاردکد شده — اگر مانیتورتان فرق دارد اصلاحش کنید (خروجی `hyprctl monitors`).
3. در `~/.config/mango/config.conf` هم `monitor_rule` برای HDMI-A-1 وجود دارد.
4. کانفیگ fastfetch نام/دستگاه نویسنده (`Zei`, `Zeibook Air`) را نشان می‌دهد — از `~/.config/fastfetch/config.jsonc` تغییرش دهید.
5. ماژول mpris ویبار روی `spotify` تنظیم شده؛ اگر Spotify ندارید خالی می‌ماند.
6. کیتی با `shell fish` بالا می‌آید؛ در صورت تمایل `~/.config/kitty/kitty.conf` را ویرایش کنید.

## کلیدهای میان‌بر اصلی (از hyprland.lua)

| کلید | کار |
|---|---|
| `SUPER + Q` | باز کردن kitty |
| `SUPER + R` | منوی hyprlauncher |
| `ALT + Space` | fuzzel |
| `SUPER + E` | فایل‌منیجر dolphin |
| `SUPER + C` | بستن پنجره |
| `SUPER + M` | خاموش/خروج |
| `ALT + Z` | اسکرین‌شات (grim + slurp + satty) |
| `ALT + [ / ]` | کم/زیاد کردن صدا |
