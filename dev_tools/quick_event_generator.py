import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys

# Ensure UTF-8 output on Windows console
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

ALAS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN_DIR = os.path.join(ALAS_ROOT, 'campaign')
README_PATH = os.path.join(CAMPAIGN_DIR, 'Readme.md')
TAG_FILE = '.quick_event_marker'


def find_latest_event_template(server='cn'):
    """
    Find the latest regular event folder in campaign/ directory.
    """
    pattern = re.compile(rf'^event_(\d{{8}})_{server}$')
    events = []
    if os.path.exists(CAMPAIGN_DIR):
        for item in os.listdir(CAMPAIGN_DIR):
            match = pattern.match(item)
            if match and os.path.isdir(os.path.join(CAMPAIGN_DIR, item)):
                folder = os.path.join(CAMPAIGN_DIR, item)
                if os.path.exists(os.path.join(folder, TAG_FILE)):
                    continue
                events.append((int(match.group(1)), item))
    if not events:
        raise RuntimeError(f"未在 campaign 目录中找到符合条件的活动模板 (server: {server})")
    events.sort(key=lambda x: x[0], reverse=True)
    return events[0][1]


def get_all_quick_events():
    """
    Find all quick events created with our marker.
    """
    quick_events = []
    if os.path.exists(CAMPAIGN_DIR):
        for item in os.listdir(CAMPAIGN_DIR):
            folder = os.path.join(CAMPAIGN_DIR, item)
            if os.path.isdir(folder) and os.path.exists(os.path.join(folder, TAG_FILE)):
                quick_events.append(item)
    return quick_events


def add_or_update_readme(date_str, directory_name, cn_name, en_name=None, server='cn'):
    """
    Add or update the event in campaign/Readme.md
    """
    if not os.path.exists(README_PATH):
        raise FileNotFoundError(f"找不到文件: {README_PATH}")

    dir_formatted = directory_name.replace('_', ' ')
    en_name = en_name or f"Event {date_str}"

    row_server = {
        'cn': cn_name,
        'en': en_name if server == 'en' else '-',
        'jp': '-',
        'tw': '-',
    }
    if server in row_server:
        row_server[server] = cn_name

    new_line = (
        f"| {date_str}   | {dir_formatted:<24} | {en_name:<45} | "
        f"{row_server['cn']:<26} | {row_server['en']:<50} | "
        f"{row_server['jp']:<36} | {row_server['tw']:<26} |\n"
    )

    with open(README_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated = False
    new_lines = []
    for line in lines:
        if f"| {dir_formatted} " in line or f"| {dir_formatted}|" in line:
            new_lines.append(new_line)
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        while new_lines and not new_lines[-1].strip():
            new_lines.pop()
        new_lines.append(new_line)
        new_lines.append("\n")

    with open(README_PATH, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"[*] 已在 {README_PATH} 中{'更新' if updated else '追加'}活动记录。")


def remove_from_readme(directory_name):
    """
    Remove event from campaign/Readme.md
    """
    if not os.path.exists(README_PATH):
        return

    dir_formatted = directory_name.replace('_', ' ')
    with open(README_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = [
        line for line in lines
        if not (f"| {dir_formatted} " in line or f"| {dir_formatted}|" in line)
    ]

    with open(README_PATH, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"[*] 已从 {README_PATH} 中移除活动记录: {directory_name}")


def run_config_updater():
    """
    Run config_updater module to refresh configs and i18n
    """
    print("[*] 正在执行 python -m module.config.config_updater 刷新 Alas 配置与多语言菜单...")
    result = subprocess.run(
        [sys.executable, '-m', 'module.config.config_updater'],
        cwd=ALAS_ROOT
    )
    if result.returncode != 0:
        print("[!] 运行 config_updater 时出现错误，请检查输出信息！")
        return False
    print("[+] 配置更新完成！")
    return True


def create_quick_event(name, date_str=None, server='cn', template_dir=None):
    """
    Main routine to create quick event.
    """
    today = datetime.datetime.now().strftime('%Y%m%d')
    date_str = (date_str or today).strip()

    if not template_dir:
        template_dir = find_latest_event_template(server=server)
    template_path = os.path.join(CAMPAIGN_DIR, template_dir)

    target_name = f"event_{date_str}_{server}"
    target_path = os.path.join(CAMPAIGN_DIR, target_name)

    print("=" * 60)
    print("【Alas 临时新活动一键生成工具】")
    print(f"活动名称:     {name}")
    print(f"活动日期:     {date_str}")
    print(f"服务器:       {server}")
    print(f"选定模板:     {template_dir}")
    print(f"目标目录:     {target_name}")
    print("=" * 60)

    # Copy template directory
    if os.path.exists(target_path):
        print(f"[!] 警告: 目标目录 {target_name} 已存在，正在覆盖更新...")
        shutil.rmtree(target_path)

    print(f"[*] 正在从 {template_dir} 复制关卡地图结构...")
    shutil.copytree(template_path, target_path)

    # Mark as quick event
    with open(os.path.join(target_path, TAG_FILE), 'w', encoding='utf-8') as f:
        f.write(f"Created on {today} using template {template_dir}\nName: {name}\n")

    # Update Readme.md
    add_or_update_readme(date_str=date_str, directory_name=target_name, cn_name=name, server=server)

    # Run updater
    if run_config_updater():
        print("\n" + "=" * 60)
        print("恭喜！临时新活动配置已成功生效！")
        print(f"1. 请在浏览器中强制刷新 Alas Web 界面 (按 Ctrl + F5)。")
        print(f"2. 进入 [任务设置] -> [活动 (Event)] 或 [活动SP (EventSp)]。")
        print(f"3. 确认当前活动已被自动设为: 「{name}」。")
        print(f"4. 游戏内请先通关并勾选「自律寻敌」(周回模式)，即可开启 Alas 自动周回！")
        print("=" * 60 + "\n")
        return True
    return False


def clean_quick_events():
    """
    Clean all temporary quick events created.
    """
    quick_events = get_all_quick_events()
    if not quick_events:
        print("[i] 当前没有检测到任何自制的临时活动目录。")
        return

    print("=" * 60)
    print("检测到以下自制临时活动：")
    for idx, item in enumerate(quick_events, 1):
        print(f" [{idx}] {item}")
    print("=" * 60)

    confirm = input("确定要清理删除上述所有临时自制活动吗？(y/N): ").strip().lower()
    if confirm != 'y':
        print("[i] 已取消清理。")
        return

    for item in quick_events:
        folder = os.path.join(CAMPAIGN_DIR, item)
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"[+] 已删除目录: {item}")
        remove_from_readme(item)

    run_config_updater()
    print("[+] 临时活动已全部清理完毕，Alas 配置已恢复为官方最新状态！\n")


def interactive_menu():
    while True:
        print("\n========================================================")
        print("         Alas 新活动免等待快速周回工具 (方案一)")
        print("========================================================")
        print(" 1. 一键创建/适配临时新活动 (复用上期模版，支持自律周回)")
        print(" 2. 清理自制的临时活动 (官方正式更新后还原配置)")
        print(" 3. 仅运行 config_updater (刷新现有配置与菜单)")
        print(" 0. 退出")
        print("========================================================")
        choice = input("请输入选项 [0-3]: ").strip()

        if choice == '1':
            name = input("请输入新活动中文名称 (例如: 碧海光粼 / 新活动测试): ").strip()
            if not name:
                name = "临时自律新活动"
            date_default = datetime.datetime.now().strftime('%Y%m%d')
            date_input = input(f"请输入活动日期 (直接回车默认: {date_default}): ").strip()
            date_str = date_input if date_input else date_default
            create_quick_event(name=name, date_str=date_str, server='cn')
        elif choice == '2':
            clean_quick_events()
        elif choice == '3':
            run_config_updater()
        elif choice == '0':
            print("退出。")
            break
        else:
            print("[!] 无效选项，请重新输入。")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Alas 临时新活动一键生成工具")
    parser.add_argument('--name', type=str, help="新活动名称")
    parser.add_argument('--date', type=str, help="新活动日期 (格式 YYYYMMDD，默认当天)")
    parser.add_argument('--server', type=str, default='cn', help="服务器标识 (cn/en/jp/tw，默认 cn)")
    parser.add_argument('--clean', action='store_true', help="清理所有自制的临时活动")
    parser.add_argument('--update', action='store_true', help="仅运行 config_updater 刷新配置")

    args = parser.parse_args()

    if args.clean:
        clean_quick_events()
    elif args.update:
        run_config_updater()
    elif args.name:
        create_quick_event(name=args.name, date_str=args.date, server=args.server)
    else:
        interactive_menu()
